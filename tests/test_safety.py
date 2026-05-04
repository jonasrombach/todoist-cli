from pathlib import Path

from todoist_cli.auth import DEFAULT_ENV_FILES, load_dotenv_token
from todoist_cli.cli import main


def test_mutating_operation_runs_without_cli_confirmation(capsys):
    class FakeClient:
        def add_task(self, content, **kwargs):
            return {"id": "42", "content": content, **kwargs}

    exit_code = main(["tasks", "add", "Buy milk"], client_factory=lambda: FakeClient())

    assert exit_code == 0
    assert "Buy milk" in capsys.readouterr().out


def test_load_dotenv_token_reads_explicit_file(tmp_path: Path):
    env_file = tmp_path / "todoist.env"
    env_file.write_text(
        "# local credentials\nTODOIST_API_TOKEN='token-from-file'\n",
        encoding="utf-8",
    )

    assert load_dotenv_token(env_file) == "token-from-file"


def test_missing_token_error_does_not_assume_machine_specific_path(monkeypatch, capsys):
    monkeypatch.delenv("TODOIST_API_TOKEN", raising=False)
    monkeypatch.delenv("TODOIST_TOKEN", raising=False)
    monkeypatch.setenv("TODOIST_CLI_ENV_FILE", "/tmp/nonexistent-todoist-cli-env")

    exit_code = main(["projects", "list"])

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "TODOIST_CLI_ENV_FILE" in err
    assert "/tmp/nonexistent-todoist-cli-env" in err


def test_default_env_file_is_neutral_config_path():
    assert (Path.home() / ".config" / "todoist-cli" / "env",) == DEFAULT_ENV_FILES
