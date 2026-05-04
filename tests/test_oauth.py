from todoist_cli.oauth import build_authorization_url, redact_secret


def test_build_authorization_url_contains_required_todoist_parameters():
    url = build_authorization_url(
        client_id="client123",
        redirect_uri="https://example.com/todoist/callback",
        scope="data:read,data:delete",
        state="state123",
    )

    assert url.startswith("https://todoist.com/oauth/authorize?")
    assert "client_id=client123" in url
    assert "scope=data%3Aread%2Cdata%3Adelete" in url
    assert "state=state123" in url


def test_redact_secret_keeps_shape_without_leaking_value():
    assert redact_secret("abcdef123456") == "abcd…3456"
    assert redact_secret("abc") == "***"
