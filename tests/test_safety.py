
from todoist_cli.cli import main


def test_mutating_operation_requires_yes(capsys):
    class FakeClient:
        def add_task(self, **kwargs):  # pragma: no cover - must not be called
            raise AssertionError("should not call API without --yes")

    exit_code = main(["tasks", "add", "Buy milk"], client_factory=lambda: FakeClient())

    assert exit_code == 2
    assert "requires --yes" in capsys.readouterr().err


def test_mutating_operation_runs_with_yes(capsys):
    class FakeClient:
        def add_task(self, content, **kwargs):
            return {"id": "42", "content": content, **kwargs}

    exit_code = main(["tasks", "add", "Buy milk", "--yes"], client_factory=lambda: FakeClient())

    assert exit_code == 0
    assert "Buy milk" in capsys.readouterr().out
