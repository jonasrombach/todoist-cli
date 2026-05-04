import hashlib
import hmac
import json
from pathlib import Path

from todoist_cli.webhooks import TodoistWebhookStore, verify_todoist_signature


def test_verify_todoist_signature_accepts_expected_hmac():
    body = b'{"event_name":"item:completed"}'
    secret = "super-secret"
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    assert verify_todoist_signature(body, signature, secret) is True
    assert verify_todoist_signature(body, "bad", secret) is False


def test_webhook_store_records_receipts_without_trusting_payload(tmp_path: Path):
    store = TodoistWebhookStore(tmp_path)
    receipt = store.record_receipt(
        {"event_name": "item:completed", "event_data": {"id": "1", "content": "private"}},
        headers={"X-Todoist-Delivery-ID": "delivery-1"},
    )

    assert receipt["event_name"] == "item:completed"
    assert receipt["delivery_id"] == "delivery-1"
    assert "event_data" not in receipt
    lines = (tmp_path / "webhook-receipts.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0]) == receipt
