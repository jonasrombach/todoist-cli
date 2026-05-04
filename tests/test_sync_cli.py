import json
from pathlib import Path

from todoist_cli.cli import main, sync_state_to_payload


def test_sync_status_reports_empty_store(tmp_path: Path, capsys):
    exit_code = main(["sync", "status", "--state-dir", str(tmp_path)])

    assert exit_code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["configured"] is True
    assert out["sync_token_present"] is False
    assert out["counts"]["items"] == 0


def test_sync_reset_removes_state_file(tmp_path: Path, capsys):
    state_file = tmp_path / "sync-state.json"
    state_file.write_text('{"sync_token":"old"}', encoding="utf-8")

    exit_code = main(["sync", "reset", "--state-dir", str(tmp_path)])

    assert exit_code == 0
    assert not state_file.exists()
    assert json.loads(capsys.readouterr().out)["status"] == "reset"


def test_sync_pull_uses_star_then_persisted_token(tmp_path: Path, capsys):
    calls = []

    def fake_fetch(token=None, sync_token="*", resource_types=None):
        calls.append(sync_token)
        return {
            "sync_token": f"token-{len(calls)}",
            "full_sync": sync_token == "*",
            "items": [{"id": str(len(calls)), "content": "Task", "checked": False, "is_deleted": False}],
        }

    exit_code_1 = main(["sync", "pull", "--state-dir", str(tmp_path)], sync_fetcher=fake_fetch)
    exit_code_2 = main(["sync", "pull", "--state-dir", str(tmp_path)], sync_fetcher=fake_fetch)

    assert exit_code_1 == 0
    assert exit_code_2 == 0
    assert calls == ["*", "token-1"]
    outputs = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
    assert outputs[-1]["sync_token_present"] is True
    assert outputs[-1]["counts"]["items"] == 2


def test_sync_state_payload_treats_archived_project_tasks_as_inactive():
    state = {
        "resources": {
            "items": {
                "1": {"id": "1", "content": "Active", "project_id": "active"},
                "2": {"id": "2", "content": "Archived", "project_id": "archived"},
            },
            "projects": {
                "active": {"id": "active", "name": "Active"},
                "archived": {"id": "archived", "name": "Archived", "is_archived": True},
            },
            "sections": {},
            "labels": {},
            "reminders": {},
        },
        "completed_items": {},
        "deleted_items": {},
    }

    payload = sync_state_to_payload(state)

    assert [item["content"] for item in payload["items"]] == ["Active"]
    assert payload["inactive_project_ids"] == ["archived"]

    payload_with_inactive = sync_state_to_payload(state, include_inactive_projects=True)
    assert [item["content"] for item in payload_with_inactive["items"]] == ["Active", "Archived"]
