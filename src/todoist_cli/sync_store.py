from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RESOURCE_KEYS = ("items", "projects", "sections", "labels", "reminders")


def default_state_dir() -> Path:
    root = os.environ.get("XDG_STATE_HOME")
    if root:
        return Path(root).expanduser() / "todoist-cli"
    return Path.home() / ".local" / "state" / "todoist-cli"


def empty_state() -> dict[str, Any]:
    return {
        "version": 1,
        "sync_token": None,
        "last_full_sync_at": None,
        "last_sync_at": None,
        "resources": {key: {} for key in RESOURCE_KEYS},
        "completed_items": {},
        "deleted_items": {},
        "completed_backfill": {"window_days": None, "last_run_at": None, "items": {}, "strategies": {}},
        "change_log": [],
    }


class SyncStore:
    def __init__(self, state_dir: Path | None = None) -> None:
        self.state_dir = state_dir or default_state_dir()
        self.state_file = self.state_dir / "sync-state.json"
        self.corrupt_state_recovered = False

    def load_state(self) -> dict[str, Any]:
        if not self.state_file.exists():
            return empty_state()
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            self.corrupt_state_recovered = True
            return empty_state()
        state = empty_state()
        state.update(data)
        resources = state.setdefault("resources", {})
        for key in RESOURCE_KEYS:
            resources.setdefault(key, {})
        state.setdefault("completed_items", {})
        state.setdefault("deleted_items", {})
        state.setdefault("completed_backfill", {"window_days": None, "last_run_at": None, "items": {}, "strategies": {}})
        state["completed_backfill"].setdefault("items", {})
        state["completed_backfill"].setdefault("strategies", {})
        state.setdefault("change_log", [])
        return state

    def save_state(self, state: dict[str, Any]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
        tmp.replace(self.state_file)

    def reset(self) -> None:
        if self.state_file.exists():
            self.state_file.unlink()


def _resource_id(obj: dict[str, Any]) -> str | None:
    value = obj.get("id")
    if value is None:
        return None
    return str(value)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _completed_item_id(item: dict[str, Any]) -> str | None:
    for key in ("task_id", "id"):
        value = item.get(key)
        if value is not None:
            return str(value)
    return None


def apply_completed_backfill(
    store: SyncStore,
    items: list[dict[str, Any]],
    window_days: int,
    strategy: str = "completion-date",
) -> dict[str, Any]:
    state = store.load_state()
    now = _now_iso()
    backfill = state.setdefault("completed_backfill", {"window_days": None, "last_run_at": None, "items": {}, "strategies": {}})
    backfill["window_days"] = window_days
    backfill["last_run_at"] = now
    backfill_items = backfill.setdefault("items", {})
    strategy_state = backfill.setdefault("strategies", {}).setdefault(strategy, {"window_days": None, "last_run_at": None, "items": {}})
    strategy_state["window_days"] = window_days
    strategy_state["last_run_at"] = now
    strategy_items = strategy_state.setdefault("items", {})
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = _completed_item_id(item)
        if item_id is None:
            continue
        backfill_items[item_id] = item
        strategy_items[item_id] = item
        state["completed_items"].setdefault(item_id, item)
    store.save_state(state)
    return state


def apply_sync_payload(store: SyncStore, payload: dict[str, Any]) -> dict[str, Any]:
    state = empty_state() if payload.get("full_sync") else store.load_state()
    now = _now_iso()
    resources = state["resources"]
    change_log = state["change_log"]

    if payload.get("full_sync"):
        state["last_full_sync_at"] = now

    for key in RESOURCE_KEYS:
        for obj in payload.get(key, []) or []:
            if not isinstance(obj, dict):
                continue
            obj_id = _resource_id(obj)
            if obj_id is None:
                continue
            previous = deepcopy(resources.setdefault(key, {}).get(obj_id))
            if key == "items" and obj.get("checked"):
                resources[key].pop(obj_id, None)
                state["completed_items"][obj_id] = obj
                event = "completed"
            elif obj.get("is_deleted"):
                resources[key].pop(obj_id, None)
                if key == "items":
                    state["deleted_items"][obj_id] = obj
                event = "deleted"
            else:
                resources[key][obj_id] = obj
                event = "added" if previous is None else "updated"
            if previous != obj:
                change_log.append({"at": now, "resource": key, "id": obj_id, "event": event})

    state["sync_token"] = payload.get("sync_token", state.get("sync_token"))
    state["last_sync_at"] = now
    # Keep the ledger compact; it is diagnostic, not an append-only audit log.
    state["change_log"] = change_log[-500:]
    store.save_state(state)
    return state
