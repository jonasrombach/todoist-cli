from __future__ import annotations

import json
import os
import sqlite3
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

RESOURCE_KEYS = ("items", "projects", "sections", "labels", "reminders")
StoreBackend = Literal["json", "sqlite"]


def default_state_dir() -> Path:
    root = os.environ.get("XDG_STATE_HOME")
    if root:
        return Path(root).expanduser() / "todoist-cli"
    return Path.home() / ".local" / "state" / "todoist-cli"


def default_backend() -> StoreBackend:
    configured = os.environ.get("TODOIST_CLI_STATE_BACKEND", "sqlite").strip().lower()
    if configured not in {"json", "sqlite"}:
        raise ValueError("TODOIST_CLI_STATE_BACKEND must be 'json' or 'sqlite'")
    return configured  # type: ignore[return-value]


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
    def __init__(self, state_dir: Path | None = None, backend: StoreBackend | None = None) -> None:
        self.state_dir = state_dir or default_state_dir()
        self.backend = backend or default_backend()
        self.state_file = self.state_dir / "sync-state.json"
        self.db_file = self.state_dir / "sync-state.sqlite3"
        self.corrupt_state_recovered = False

    def load_state(self) -> dict[str, Any]:
        if self.backend == "sqlite":
            return self._load_sqlite_state()
        return self._load_json_state()

    def save_state(self, state: dict[str, Any]) -> None:
        state = normalize_state(state)
        if self.backend == "sqlite":
            self._save_sqlite_state(state)
        else:
            self._save_json_state(state)

    def reset(self) -> None:
        for path in (self.state_file, self.db_file):
            if path.exists():
                path.unlink()

    def migrate_json_to_sqlite(self, remove_json: bool = False) -> dict[str, Any]:
        state = self._load_json_state()
        self._save_sqlite_state(state)
        if remove_json and self.state_file.exists():
            self.state_file.unlink()
        return state

    def _load_json_state(self) -> dict[str, Any]:
        if not self.state_file.exists():
            return empty_state()
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            self.corrupt_state_recovered = True
            return empty_state()
        return normalize_state(data)

    def _save_json_state(self, state: dict[str, Any]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
        tmp.replace(self.state_file)

    def _connect(self) -> sqlite3.Connection:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _init_db(conn)
        return conn

    def _load_sqlite_state(self) -> dict[str, Any]:
        if not self.db_file.exists():
            if self.state_file.exists():
                return self._load_json_state()
            return empty_state()
        try:
            with self._connect() as conn:
                state = empty_state()
                meta = {row["key"]: row["value"] for row in conn.execute("SELECT key, value FROM meta")}
                state["version"] = int(meta.get("version") or 1)
                state["sync_token"] = meta.get("sync_token")
                state["last_full_sync_at"] = meta.get("last_full_sync_at")
                state["last_sync_at"] = meta.get("last_sync_at")
                for row in conn.execute("SELECT resource, id, payload_json FROM resources"):
                    state["resources"].setdefault(row["resource"], {})[row["id"]] = json.loads(row["payload_json"])
                for row in conn.execute("SELECT kind, id, payload_json FROM evidence"):
                    target = "completed_items" if row["kind"] == "completed" else "deleted_items"
                    state[target][row["id"]] = json.loads(row["payload_json"])
                state["completed_backfill"] = _load_backfill(conn)
                state["change_log"] = [
                    {"at": row["at"], "resource": row["resource"], "id": row["id"], "event": row["event"]}
                    for row in conn.execute("SELECT at, resource, id, event FROM change_log ORDER BY seq")
                ]
                return normalize_state(state)
        except (sqlite3.DatabaseError, OSError, json.JSONDecodeError, ValueError):
            self.corrupt_state_recovered = True
            return empty_state()

    def _save_sqlite_state(self, state: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute("BEGIN")
            conn.execute("DELETE FROM meta")
            conn.execute("DELETE FROM resources")
            conn.execute("DELETE FROM evidence")
            conn.execute("DELETE FROM completed_backfill")
            conn.execute("DELETE FROM completed_backfill_items")
            conn.execute("DELETE FROM change_log")
            for key in ("version", "sync_token", "last_full_sync_at", "last_sync_at"):
                value = state.get(key)
                if value is not None:
                    conn.execute("INSERT INTO meta(key, value) VALUES (?, ?)", (key, str(value)))
            for resource, items in state.get("resources", {}).items():
                for item_id, payload in (items or {}).items():
                    conn.execute(
                        "INSERT INTO resources(resource, id, payload_json) VALUES (?, ?, ?)",
                        (resource, str(item_id), json.dumps(payload, ensure_ascii=False, sort_keys=True)),
                    )
            for kind, key in (("completed", "completed_items"), ("deleted", "deleted_items")):
                for item_id, payload in state.get(key, {}).items():
                    conn.execute(
                        "INSERT INTO evidence(kind, id, payload_json) VALUES (?, ?, ?)",
                        (kind, str(item_id), json.dumps(payload, ensure_ascii=False, sort_keys=True)),
                    )
            _save_backfill(conn, state.get("completed_backfill", {}))
            for idx, event in enumerate(state.get("change_log", [])):
                conn.execute(
                    "INSERT INTO change_log(seq, at, resource, id, event) VALUES (?, ?, ?, ?, ?)",
                    (idx, event.get("at"), event.get("resource"), str(event.get("id")), event.get("event")),
                )


def normalize_state(data: dict[str, Any]) -> dict[str, Any]:
    state = empty_state()
    if isinstance(data, dict):
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


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS resources (
            resource TEXT NOT NULL,
            id TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            PRIMARY KEY (resource, id)
        );
        CREATE TABLE IF NOT EXISTS evidence (
            kind TEXT NOT NULL,
            id TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            PRIMARY KEY (kind, id)
        );
        CREATE TABLE IF NOT EXISTS completed_backfill (
            strategy TEXT PRIMARY KEY,
            window_days INTEGER,
            last_run_at TEXT
        );
        CREATE TABLE IF NOT EXISTS completed_backfill_items (
            strategy TEXT NOT NULL,
            id TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            PRIMARY KEY (strategy, id)
        );
        CREATE TABLE IF NOT EXISTS change_log (
            seq INTEGER PRIMARY KEY,
            at TEXT,
            resource TEXT,
            id TEXT,
            event TEXT
        );
        """
    )


def _load_backfill(conn: sqlite3.Connection) -> dict[str, Any]:
    backfill = {"window_days": None, "last_run_at": None, "items": {}, "strategies": {}}
    for row in conn.execute("SELECT strategy, window_days, last_run_at FROM completed_backfill"):
        strategy = row["strategy"]
        if strategy == "__all__":
            backfill["window_days"] = row["window_days"]
            backfill["last_run_at"] = row["last_run_at"]
        else:
            backfill["strategies"][strategy] = {"window_days": row["window_days"], "last_run_at": row["last_run_at"], "items": {}}
    for row in conn.execute("SELECT strategy, id, payload_json FROM completed_backfill_items"):
        item = json.loads(row["payload_json"])
        if row["strategy"] == "__all__":
            backfill["items"][row["id"]] = item
        else:
            strategy_state = backfill["strategies"].setdefault(row["strategy"], {"window_days": None, "last_run_at": None, "items": {}})
            strategy_state["items"][row["id"]] = item
    return backfill


def _save_backfill(conn: sqlite3.Connection, backfill: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO completed_backfill(strategy, window_days, last_run_at) VALUES (?, ?, ?)",
        ("__all__", backfill.get("window_days"), backfill.get("last_run_at")),
    )
    for item_id, payload in backfill.get("items", {}).items():
        conn.execute(
            "INSERT INTO completed_backfill_items(strategy, id, payload_json) VALUES (?, ?, ?)",
            ("__all__", str(item_id), json.dumps(payload, ensure_ascii=False, sort_keys=True)),
        )
    for strategy, strategy_state in backfill.get("strategies", {}).items():
        conn.execute(
            "INSERT INTO completed_backfill(strategy, window_days, last_run_at) VALUES (?, ?, ?)",
            (strategy, strategy_state.get("window_days"), strategy_state.get("last_run_at")),
        )
        for item_id, payload in strategy_state.get("items", {}).items():
            conn.execute(
                "INSERT INTO completed_backfill_items(strategy, id, payload_json) VALUES (?, ?, ?)",
                (strategy, str(item_id), json.dumps(payload, ensure_ascii=False, sort_keys=True)),
            )


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


def _last_known_item_snapshot(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    return {
        "id": item.get("id"),
        "content": item.get("content"),
        "project_id": item.get("project_id"),
        "section_id": item.get("section_id"),
        "parent_id": item.get("parent_id"),
        "due": item.get("due"),
        "deadline": item.get("deadline"),
        "labels": item.get("labels") or [],
        "priority": item.get("priority"),
        "description_present": bool(item.get("description")),
    }


def _deleted_item_tombstone(obj_id: str, delta: dict[str, Any], previous: dict[str, Any] | None, seen_at: str) -> dict[str, Any]:
    tombstone: dict[str, Any] = {
        "id": obj_id,
        "status": "deleted",
        "deleted_at_seen": seen_at,
        "evidence": {
            "kind": "todoist_deleted_item",
            "task_id": obj_id,
            "is_deleted": bool(delta.get("is_deleted")),
        },
        "deleted_delta": delta,
    }
    last_known = _last_known_item_snapshot(previous)
    if last_known is not None:
        tombstone["last_known"] = last_known
    return tombstone


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
                    state["deleted_items"][obj_id] = _deleted_item_tombstone(obj_id, obj, previous, now)
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
