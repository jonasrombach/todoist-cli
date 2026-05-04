import hashlib
import hmac
import json
from pathlib import Path

from todoist_cli.cli import main


def test_webhook_receive_verifies_signature_records_receipt_and_pulls_sync(tmp_path: Path, capsys):
    body = b'{"event_name":"item:completed","event_data":{"id":"1","content":"private"}}'
    secret = "super-secret"
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    body_file = tmp_path / "payload.json"
    body_file.write_bytes(body)
    calls = []

    def fake_fetch(token=None, sync_token="*", resource_types=None):
        calls.append(sync_token)
        return {"sync_token": "token-1", "full_sync": True, "items": []}

    exit_code = main(
        [
            "webhook",
            "receive",
            "--state-dir",
            str(tmp_path),
            "--secret",
            secret,
            "--signature",
            signature,
            "--body-file",
            str(body_file),
        ],
        sync_fetcher=fake_fetch,
    )

    assert exit_code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "accepted"
    assert out["receipt"]["event_name"] == "item:completed"
    assert calls == ["*"]


def test_webhook_receive_rejects_bad_signature(tmp_path: Path, capsys):
    body_file = tmp_path / "payload.json"
    body_file.write_text('{"event_name":"item:completed"}', encoding="utf-8")

    exit_code = main(
        [
            "webhook",
            "receive",
            "--state-dir",
            str(tmp_path),
            "--secret",
            "super-secret",
            "--signature",
            "bad",
            "--body-file",
            str(body_file),
        ]
    )

    assert exit_code == 1
    out = json.loads(capsys.readouterr().out)
    assert out["error_type"] == "PermissionError"
