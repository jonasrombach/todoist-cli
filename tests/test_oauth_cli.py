import json

from todoist_cli.cli import main


def test_oauth_authorize_url_command_outputs_url_without_secret(capsys):
    exit_code = main(
        [
            "oauth",
            "authorize-url",
            "--client-id",
            "client123",
            "--redirect-uri",
            "https://example.com/callback",
            "--scope",
            "data:read",
            "--state",
            "state123",
        ]
    )

    assert exit_code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["authorize_url"].startswith("https://todoist.com/oauth/authorize?")
    assert out["client_id"] == "clie…t123"
