from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

API_URL = "https://api.todoist.com/api/v1/sync"
RESOURCE_TYPES = ["items", "projects", "sections", "labels"]


def _load_token() -> str | None:
    token = os.environ.get("TODOIST_API_TOKEN") or os.environ.get("TODOIST_TOKEN")
    if token:
        return token.strip()
    env_file = Path.home() / ".hermes" / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() in {"TODOIST_API_TOKEN", "TODOIST_TOKEN"}:
                return value.strip().strip('"').strip("'") or None
    return None


def fetch_sync_payload(token: str | None = None) -> dict[str, Any]:
    token = token or _load_token()
    if not token:
        raise RuntimeError("Missing TODOIST_API_TOKEN in environment or ~/.hermes/.env")
    body = urllib.parse.urlencode(
        {"sync_token": "*", "resource_types": json.dumps(RESOURCE_TYPES)}
    ).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "todoist-cli/0.1",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _now(now_iso: str | None = None) -> datetime:
    if now_iso:
        dt = datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    tz = ZoneInfo("Europe/Berlin") if ZoneInfo else timezone.utc
    return datetime.now(tz)


def _parse_due(due: dict[str, Any] | None) -> tuple[datetime | None, bool]:
    if not isinstance(due, dict):
        return None, False
    value = due.get("datetime") or due.get("date")
    if not value:
        return None, False
    is_date_only = "datetime" not in due
    try:
        if is_date_only:
            tz = ZoneInfo("Europe/Berlin") if ZoneInfo else timezone.utc
            return datetime.fromisoformat(str(value)).replace(tzinfo=tz), True
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            tz = ZoneInfo(due.get("timezone") or "Europe/Berlin") if ZoneInfo else timezone.utc
            dt = dt.replace(tzinfo=tz)
        return dt, False
    except Exception:
        return None, is_date_only


def build_heartbeat_context(payload: dict[str, Any], now_iso: str | None = None) -> dict[str, Any]:
    now = _now(now_iso)
    today = now.date()
    horizon = today + timedelta(days=7)
    projects = {str(p.get("id")): p.get("name") for p in payload.get("projects", []) if isinstance(p, dict)}
    sections = {str(s.get("id")): s.get("name") for s in payload.get("sections", []) if isinstance(s, dict)}
    labels = {str(label.get("id")): label.get("name") for label in payload.get("labels", []) if isinstance(label, dict)}
    buckets: dict[str, list[dict[str, Any]]] = {
        "overdue": [],
        "today": [],
        "next_7_days": [],
        "high_priority_no_near_due": [],
    }
    for item in payload.get("items", []):
        if not isinstance(item, dict) or item.get("checked") or item.get("is_deleted"):
            continue
        due_dt, date_only = _parse_due(item.get("due"))
        due_date = due_dt.date() if due_dt else None
        priority = int(item.get("priority") or 1)
        bucket: str | None = None
        if due_date and due_date < today:
            bucket = "overdue"
        elif due_date == today:
            bucket = "today"
        elif due_date and today < due_date <= horizon:
            bucket = "next_7_days"
        elif priority >= 3:
            bucket = "high_priority_no_near_due"
        if not bucket:
            continue
        task = {
            "id": str(item.get("id")),
            "content": item.get("content"),
            "description_present": bool(item.get("description")),
            "project": projects.get(str(item.get("project_id")), str(item.get("project_id") or "")),
            "section": sections.get(str(item.get("section_id")), "") if item.get("section_id") else "",
            "priority": priority,
            "due": item.get("due"),
            "due_at": due_dt.isoformat() if due_dt else None,
            "due_date_only": date_only,
            "labels": [labels.get(str(label), str(label)) for label in item.get("labels") or []],
            "url": item.get("url"),
        }
        buckets[bucket].append(task)
    order = {"overdue": 0, "today": 1, "next_7_days": 2, "high_priority_no_near_due": 3}
    for _key, tasks in buckets.items():
        tasks.sort(key=lambda t: (t.get("due_at") or "9999", -int(t.get("priority") or 1), str(t.get("content") or "")))
    return {
        "configured": True,
        "generated_at": now.isoformat(),
        "source": "todoist_api_v1_sync",
        "counts": {k: len(v) for k, v in buckets.items()},
        "tasks": {k: v[:12] for k, v in buckets.items()},
        "bucket_order": sorted(order, key=order.get),
    }
