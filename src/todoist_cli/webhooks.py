from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def verify_todoist_signature(body: bytes, signature: str | None, secret: str) -> bool:
    if not signature or not secret:
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


class TodoistWebhookStore:
    """Append-only webhook receipt store.

    Receipts intentionally avoid storing raw event_data because Todoist payloads can
    contain personal task contents. The payload is a wake-up signal; /sync remains
    the canonical state source.
    """

    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir
        self.receipts_file = state_dir / "webhook-receipts.jsonl"

    def record_receipt(self, payload: dict[str, Any], headers: dict[str, str] | None = None) -> dict[str, Any]:
        headers = headers or {}
        receipt = {
            "received_at": datetime.now(timezone.utc).isoformat(),
            "event_name": payload.get("event_name"),
            "user_id": payload.get("user_id"),
            "delivery_id": headers.get("X-Todoist-Delivery-ID") or headers.get("x-todoist-delivery-id"),
            "resource_id": _resource_id(payload),
        }
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with self.receipts_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n")
        return receipt


def _resource_id(payload: dict[str, Any]) -> str | None:
    data = payload.get("event_data")
    if not isinstance(data, dict):
        return None
    for key in ("id", "task_id", "item_id", "project_id", "section_id"):
        if data.get(key) is not None:
            return str(data[key])
    return None
