import json
from pathlib import Path

from todoist_cli.cli import main


def test_heartbeat_context_pulls_sync_then_uses_store(tmp_path: Path, capsys):
    def fake_fetch(token=None, sync_token="*", resource_types=None):
        return {
            "sync_token": "token-1",
            "full_sync": True,
            "items": [
                {"id": "1", "content": "Today", "priority": 4, "due": {"date": "2026-05-04"}, "checked": False},
                {"id": "2", "content": "Done", "priority": 1, "due": {"date": "2026-05-04"}, "checked": True},
                {"id": "3", "content": "Deleted", "priority": 1, "due": {"date": "2026-05-04"}, "is_deleted": True},
            ],
            "projects": [],
            "sections": [],
            "labels": [],
        }

    exit_code = main(
        ["heartbeat-context", "--state-dir", str(tmp_path), "--now", "2026-05-04T09:00:00+02:00"],
        sync_fetcher=fake_fetch,
    )

    assert exit_code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["source"] == "todoist_sync_store"
    assert [t["content"] for t in out["tasks"]["today"]] == ["Today"]
    assert out["counts"]["completed"] == 1
    assert out["counts"]["deleted_unknown"] == 1
