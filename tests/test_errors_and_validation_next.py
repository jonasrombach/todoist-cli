import json

from todoist_cli.cli import main


class FakeTodoistHTTPError(Exception):
    def __init__(self):
        super().__init__("rate limited")
        self.status_code = 429
        self.request_id = "req_123"


class ShouldNotBeCalledClient:
    def __getattr__(self, name):
        raise AssertionError(f"client method should not be called: {name}")


def test_structured_error_includes_status_request_id_and_retryable(capsys):
    class BrokenClient:
        def get_projects(self, limit=None):
            raise FakeTodoistHTTPError()

    exit_code = main(["projects", "list"], client_factory=lambda: BrokenClient())

    assert exit_code == 1
    out = json.loads(capsys.readouterr().out)
    assert out == {
        "status": "error",
        "error_type": "FakeTodoistHTTPError",
        "message": "rate limited",
        "request_id": "req_123",
        "status_code": 429,
        "retryable": True,
    }


def test_due_options_are_mutually_exclusive(capsys):
    exit_code = main(
        ["tasks", "add", "X", "--due-string", "tomorrow", "--due-date", "2026-05-05"],
        client_factory=lambda: ShouldNotBeCalledClient(),
    )

    assert exit_code == 1
    out = json.loads(capsys.readouterr().out)
    assert out["error_type"] == "ValueError"
    assert "mutually exclusive" in out["message"]


def test_location_reminder_update_requires_complete_location_fields(capsys):
    exit_code = main(
        ["location-reminders", "update", "lr1", "--loc-lat", "48.1"],
        client_factory=lambda: ShouldNotBeCalledClient(),
    )

    assert exit_code == 1
    out = json.loads(capsys.readouterr().out)
    assert out["error_type"] == "ValueError"
    assert "loc_lat, loc_long, and loc_trigger" in out["message"]
