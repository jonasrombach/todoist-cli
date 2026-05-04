from __future__ import annotations

import json
import urllib.parse
from pathlib import Path
from typing import Any

AUTHORIZE_URL = "https://todoist.com/oauth/authorize"
TOKEN_URL = "https://todoist.com/oauth/access_token"


def build_authorization_url(client_id: str, redirect_uri: str, scope: str, state: str) -> str:
    query = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "scope": scope,
            "state": state,
            "redirect_uri": redirect_uri,
        }
    )
    return f"{AUTHORIZE_URL}?{query}"


def redact_secret(value: str | None) -> str:
    if not value or len(value) < 8:
        return "***"
    return f"{value[:4]}…{value[-4:]}"


def build_token_exchange_request(client_id: str, client_secret: str, code: str, redirect_uri: str) -> dict[str, Any]:
    body = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }
    return {"url": TOKEN_URL, "body": body, "redacted": _redacted_body(body)}


def build_token_refresh_request(client_id: str, client_secret: str, refresh_token: str) -> dict[str, Any]:
    body = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    }
    return {"url": TOKEN_URL, "body": body, "redacted": _redacted_body(body)}


def _redacted_body(body: dict[str, Any]) -> dict[str, Any]:
    return {k: redact_secret(v) if "secret" in k or "token" in k else v for k, v in body.items()}


class OAuthTokenStore:
    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir
        self.token_file = state_dir / "oauth-tokens.json"

    def save_tokens(self, tokens: dict[str, Any]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.token_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(tokens, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.token_file)
        self.token_file.chmod(0o600)

    def load_tokens(self) -> dict[str, Any]:
        if not self.token_file.exists():
            return {}
        return json.loads(self.token_file.read_text(encoding="utf-8"))

    def redacted_summary(self) -> dict[str, Any]:
        return _redacted_body(self.load_tokens())
