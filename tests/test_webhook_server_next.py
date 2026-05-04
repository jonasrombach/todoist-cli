import hashlib
import hmac
import json
import urllib.request
from pathlib import Path

from todoist_cli.webhooks import run_webhook_server


def test_webhook_server_filters_and_debounces_events(tmp_path: Path):
    secret = "super-secret"
    calls = []

    def fake_sync():
        calls.append("sync")

    server = run_webhook_server(
        host="127.0.0.1",
        port=0,
        state_dir=tmp_path,
        secret=secret,
        allowed_events={"item:completed"},
        debounce_seconds=60,
        sync_callback=fake_sync,
    )
    try:
        port = server.server_address[1]
        body = b'{"event_name":"item:completed","event_data":{"id":"1","content":"private"}}'
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/todoist/webhook",
            data=body,
            headers={"X-Todoist-Hmac-SHA256": signature, "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            first = json.loads(resp.read().decode())
        with urllib.request.urlopen(req, timeout=5) as resp:
            second = json.loads(resp.read().decode())
    finally:
        server.shutdown()
        server.server_close()

    assert first["status"] == "accepted"
    assert second["status"] == "debounced"
    assert calls == ["sync"]
    receipt = json.loads((tmp_path / "webhook-receipts.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert receipt["event_name"] == "item:completed"
