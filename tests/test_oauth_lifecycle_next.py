import json
from pathlib import Path

from todoist_cli.oauth import (
    OAuthTokenStore,
    build_token_exchange_request,
    build_token_refresh_request,
)


def test_build_token_exchange_and_refresh_requests_do_not_print_secrets():
    exchange = build_token_exchange_request(
        client_id="client",
        client_secret="secret",
        code="code123",
        redirect_uri="https://example.com/callback",
    )
    refresh = build_token_refresh_request(client_id="client", client_secret="secret", refresh_token="refresh123")

    assert exchange["url"] == "https://todoist.com/oauth/access_token"
    assert exchange["body"]["grant_type"] == "authorization_code"
    assert refresh["body"]["grant_type"] == "refresh_token"
    assert exchange["redacted"]["client_secret"] == "***"
    assert refresh["redacted"]["refresh_token"] == "refr…h123"


def test_oauth_token_store_saves_refresh_token_outside_repo(tmp_path: Path):
    store = OAuthTokenStore(tmp_path)
    store.save_tokens({"access_token": "access123", "refresh_token": "refresh123", "expires_in": 3600})

    data = json.loads((tmp_path / "oauth-tokens.json").read_text(encoding="utf-8"))
    assert data["refresh_token"] == "refresh123"
    assert store.redacted_summary()["refresh_token"] == "refr…h123"
