from __future__ import annotations

import hashlib
import hmac
import json
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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


class Debouncer:
    def __init__(self, seconds: int) -> None:
        self.seconds = seconds
        self.last_seen: dict[str, float] = {}

    def should_run(self, key: str, now_ts: float) -> bool:
        previous = self.last_seen.get(key)
        self.last_seen[key] = now_ts
        return previous is None or now_ts - previous >= self.seconds


def run_webhook_server(
    host: str,
    port: int,
    state_dir: Path,
    secret: str,
    allowed_events: set[str] | None = None,
    debounce_seconds: int = 5,
    sync_callback: Callable[[], None] | None = None,
) -> ThreadingHTTPServer:
    store = TodoistWebhookStore(state_dir)
    debouncer = Debouncer(debounce_seconds)
    allowed = allowed_events or set()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/todoist/webhook":
                self.send_error(404)
                return
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            signature = self.headers.get("X-Todoist-Hmac-SHA256")
            if not verify_todoist_signature(body, signature, secret):
                self._json(401, {"status": "error", "message": "invalid signature"})
                return
            payload = json.loads(body.decode("utf-8"))
            event_name = str(payload.get("event_name") or "")
            if allowed and event_name not in allowed:
                self._json(202, {"status": "ignored", "event_name": event_name})
                return
            receipt = store.record_receipt(payload, headers=dict(self.headers.items()))
            debounce_key = f"{event_name}:{receipt.get('resource_id') or receipt.get('delivery_id') or ''}"
            now_ts = datetime.now(timezone.utc).timestamp()
            if not debouncer.should_run(debounce_key, now_ts):
                self._json(200, {"status": "debounced", "receipt": receipt})
                return
            if sync_callback:
                sync_callback()
            self._json(200, {"status": "accepted", "receipt": receipt})

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

        def _json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer((host, port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
