import json
from pathlib import Path

from todoist_cli.cli import main


def test_sync_backfill_completed_calls_sdk_and_records_items(tmp_path: Path, capsys):
    class FakeClient:
        def get_completed_tasks_by_completion_date(self, since=None, until=None, workspace_id=None, filter_query=None, filter_lang=None, limit=None):
            assert since.isoformat() == "2026-04-20"
            assert until.isoformat() == "2026-05-04"
            assert limit == 200
            return [[{"task_id": "1", "content": "Done", "completed_at": "2026-05-03T10:00:00Z"}]]

    exit_code = main(
        [
            "sync",
            "backfill-completed",
            "--state-dir",
            str(tmp_path),
            "--now",
            "2026-05-04T09:00:00+02:00",
            "--window-days",
            "14",
        ],
        client_factory=lambda: FakeClient(),
    )

    assert exit_code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["completed_items"] == 1
    assert out["completed_backfill"]["window_days"] == 14
