from todoist_cli.cli import main


def test_mutating_operation_runs_without_cli_confirmation(capsys):
    class FakeClient:
        def add_task(self, content, **kwargs):
            return {"id": "42", "content": content, **kwargs}

    exit_code = main(["tasks", "add", "Buy milk"], client_factory=lambda: FakeClient())

    assert exit_code == 0
    assert "Buy milk" in capsys.readouterr().out
