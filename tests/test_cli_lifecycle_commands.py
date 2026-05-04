import hmac
import json
import socket
import threading
import time
from hashlib import sha256
from pathlib import Path
from urllib import error, request

from todoist_cli.cli import main


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _post_with_retry(req: request.Request, timeout: float = 5):
    deadline = time.time() + timeout
    last_exc = None
    while time.time() < deadline:
        try:
            return request.urlopen(req, timeout=1)
        except error.URLError as exc:
            last_exc = exc
            time.sleep(0.05)
    raise last_exc


def test_oauth_exchange_and_refresh_cli_store_tokens_without_printing_secrets(tmp_path: Path, capsys):
    exchanged = []

    def fake_oauth_post(url, body):
        exchanged.append((url, body))
        if body["grant_type"] == "authorization_code":
            return {"access_token": "access12345", "refresh_token": "refresh12345", "expires_in": 3600}
        return {"access_token": "access67890", "refresh_token": "refresh67890", "expires_in": 3600}

    exchange_code = main(
        [
            "oauth",
            "exchange-token",
            "--state-dir",
            str(tmp_path),
            "--client-id",
            "client12345",
            "--client-secret",
            "secret12345",
            "--code",
            "code12345",
            "--redirect-uri",
            "https://example.com/callback",
        ],
        oauth_post=fake_oauth_post,
    )
    refresh_code = main(
        [
            "oauth",
            "refresh-token",
            "--state-dir",
            str(tmp_path),
            "--client-id",
            "client12345",
            "--client-secret",
            "secret12345",
        ],
        oauth_post=fake_oauth_post,
    )

    assert exchange_code == 0
    assert refresh_code == 0
    stdout = capsys.readouterr().out
    assert "access12345" not in stdout
    assert "refresh12345" not in stdout
    assert "secret12345" not in stdout
    assert exchanged[0][1]["grant_type"] == "authorization_code"
    assert exchanged[1][1]["grant_type"] == "refresh_token"
    stored = json.loads((tmp_path / "oauth-tokens.json").read_text(encoding="utf-8"))
    assert stored["access_token"] == "access67890"
    assert stored["refresh_token"] == "refresh67890"
    assert oct((tmp_path / "oauth-tokens.json").stat().st_mode & 0o777) == "0o600"


def test_webhook_serve_cli_accepts_signed_event_and_triggers_sync(tmp_path: Path, capsys):
    secret = "super-secret"
    body = json.dumps({"event_name": "item:updated", "event_data": {"id": "task1"}}).encode()
    signature = hmac.new(secret.encode(), body, sha256).hexdigest()
    sync_calls = []

    def fake_sync_fetcher(sync_token="*", resource_types=None):
        sync_calls.append((sync_token, tuple(resource_types or [])))
        return {"sync_token": "token1", "full_sync": sync_token == "*", "items": []}

    port = _free_port()
    result = {}

    def run_cli():
        result["exit_code"] = main(
            [
                "webhook",
                "serve",
                "--state-dir",
                str(tmp_path),
                "--secret",
                secret,
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--once",
                "--timeout",
                "5",
                "--allow-event",
                "item:updated",
            ],
            sync_fetcher=fake_sync_fetcher,
        )

    thread = threading.Thread(target=run_cli)
    thread.start()

    req = request.Request(
        f"http://127.0.0.1:{port}/todoist/webhook",
        data=body,
        headers={"X-Todoist-Hmac-SHA256": signature, "Content-Type": "application/json"},
        method="POST",
    )
    with _post_with_retry(req, timeout=5) as resp:
        response = json.loads(resp.read().decode())
    thread.join(timeout=5)

    assert result["exit_code"] == 0
    assert response["status"] == "accepted"
    assert sync_calls == [("*", ("items", "projects", "sections", "labels"))]
    receipt_lines = (tmp_path / "webhook-receipts.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(receipt_lines) == 1
    assert "event_data" not in receipt_lines[0]
    server_output = json.loads(capsys.readouterr().out)
    assert server_output["status"] == "served_once"
