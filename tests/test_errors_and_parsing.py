import json
from datetime import date, datetime

from todoist_cli.cli import coerce_option, main


def test_json_error_output_is_machine_readable_and_keeps_stderr(capsys):
    class BrokenClient:
        def get_projects(self, limit=None):
            raise RuntimeError("network exploded")

    exit_code = main(["projects", "list"], client_factory=lambda: BrokenClient())

    assert exit_code == 1
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "error"
    assert out["error_type"] == "RuntimeError"
    assert out["message"] == "network exploded"


def test_date_and_datetime_options_are_parsed_to_python_types():
    assert coerce_option("due_date", "2026-05-04") == date(2026, 5, 4)
    assert coerce_option("deadline_date", "2026-05-05") == date(2026, 5, 5)
    parsed = coerce_option("due_datetime", "2026-05-04T10:30:00+02:00")
    assert isinstance(parsed, datetime)
    assert parsed.isoformat() == "2026-05-04T10:30:00+02:00"


def test_invalid_date_option_returns_structured_error(capsys):
    exit_code = main(["tasks", "add", "Bad date", "--due-date", "tomorrow"])

    assert exit_code == 1
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "error"
    assert out["error_type"] == "ValueError"
    assert "due_date" in out["message"]
