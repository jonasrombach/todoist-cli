from __future__ import annotations

import urllib.parse

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
