import json
from pathlib import Path

from todoist_cli.cli import main


class FakeClient:
    def get_completed_tasks_by_completion_date(self, since=None, until=None, workspace_id=None, filter_query=None, filter_lang=None, limit=None):
        return [[{"task_id": "1", "content": "Done by completion"}]]

    def get_completed_tasks_by_due_date(self, since=None, until=None, workspace_id=None, project_id=None, section_id=None, parent_id=None, filter_query=None, filter_lang=None, limit=None):
        return [[{"task_id": "2", "content": "Done by due"}]]


def test_sync_backfill_completed_can_use_due_date_strategy(tmp_path: Path, capsys):
    exit_code = main(
        [
            "sync",
            "backfill-completed",
            "--state-dir",
            str(tmp_path),
            "--strategy",
            "due-date",
            "--now",
            "2026-05-04T09:00:00+02:00",
        ],
        client_factory=lambda: FakeClient(),
    )

    assert exit_code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["completed_items"] == 1
    state = json.loads((tmp_path / "sync-state.json").read_text(encoding="utf-8"))
    assert state["completed_backfill"]["strategies"]["due-date"]["items"]["2"]["content"] == "Done by due"
