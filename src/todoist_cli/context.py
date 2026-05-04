from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from .auth import load_token, missing_token_message

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

API_URL = "https://api.todoist.com/api/v1/sync"
RESOURCE_TYPES = ["items", "projects", "sections", "labels"]


def fetch_sync_payload(
    token: str | None = None,
    sync_token: str = "*",
    resource_types: list[str] | None = None,
) -> dict[str, Any]:
    token = token or load_token()
    if not token:
        raise RuntimeError(missing_token_message())

    body = urllib.parse.urlencode(
        {"sync_token": sync_token, "resource_types": json.dumps(resource_types or RESOURCE_TYPES)}
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
        "postponed": [],
        "high_priority_no_near_due": [],
        "completed": [],
        "deleted_unknown": [],
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
        elif due_date and due_date > horizon:
            bucket = "postponed"
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
    for bucket_name, source_key in (("completed", "completed_items"), ("deleted_unknown", "deleted_items")):
        raw_items = payload.get(source_key, {})
        values = raw_items.values() if isinstance(raw_items, dict) else raw_items
        for item in values or []:
            if not isinstance(item, dict):
                continue
            task_id = str(item.get("task_id") or item.get("id"))
            if bucket_name == "completed":
                evidence = {
                    "kind": "todoist_completed_item",
                    "task_id": task_id,
                    "checked": bool(item.get("checked")),
                    "completed_at": item.get("completed_at"),
                    "completed_by_uid": item.get("completed_by_uid"),
                }
                buckets[bucket_name].append(
                    {
                        "id": task_id,
                        "content": item.get("content"),
                        "project": projects.get(str(item.get("project_id")), str(item.get("project_id") or "")),
                        "completed_at": item.get("completed_at"),
                        "due": item.get("due"),
                        "evidence": evidence,
                    }
                )
            else:
                last_known = item.get("last_known") if isinstance(item.get("last_known"), dict) else {}
                delta = item.get("deleted_delta") if isinstance(item.get("deleted_delta"), dict) else item
                evidence_payload = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
                source = "deleted_delta_with_prior_snapshot" if last_known else "deleted_delta_only"
                evidence = {
                    "kind": evidence_payload.get("kind") or "todoist_deleted_item",
                    "task_id": task_id,
                    "is_deleted": bool(evidence_payload.get("is_deleted", delta.get("is_deleted"))),
                    "source": source,
                }
                project_id = last_known.get("project_id") or delta.get("project_id")
                buckets[bucket_name].append(
                    {
                        "id": task_id,
                        "content": last_known.get("content"),
                        "project": projects.get(str(project_id), str(project_id or "")),
                        "status": "deleted",
                        "attention_required": False,
                        "description_present": bool(last_known.get("description_present")),
                        "due": last_known.get("due"),
                        "labels": [labels.get(str(label), str(label)) for label in last_known.get("labels") or []],
                        "priority": last_known.get("priority"),
                        "evidence": evidence,
                    }
                )
    order = {
        "overdue": 0,
        "today": 1,
        "next_7_days": 2,
        "postponed": 3,
        "high_priority_no_near_due": 4,
        "completed": 5,
        "deleted_unknown": 6,
    }
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
