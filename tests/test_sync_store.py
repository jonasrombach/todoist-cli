from pathlib import Path

from todoist_cli.sync_store import SyncStore, apply_sync_payload, default_state_dir


def test_default_state_dir_uses_xdg_state_home(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))

    assert default_state_dir() == tmp_path / "todoist-cli"


def test_sync_store_persists_token_and_applies_full_payload(tmp_path: Path):
    store = SyncStore(tmp_path / "state")
    payload = {
        "sync_token": "token-1",
        "full_sync": True,
        "items": [
            {"id": "1", "content": "Active", "checked": False, "is_deleted": False},
            {"id": "2", "content": "Done", "checked": True, "is_deleted": False},
            {"id": "3", "content": "Deleted", "checked": False, "is_deleted": True},
        ],
        "projects": [{"id": "p1", "name": "Admin"}],
        "sections": [],
        "labels": [],
        "reminders": [],
    }

    apply_sync_payload(store, payload)

    state = store.load_state()
    assert state["sync_token"] == "token-1"
    assert state["resources"]["items"]["1"]["content"] == "Active"
    assert "2" not in state["resources"]["items"]
    assert state["completed_items"]["2"]["content"] == "Done"
    assert state["deleted_items"]["3"]["content"] == "Deleted"
    assert state["resources"]["projects"]["p1"]["name"] == "Admin"
    assert len(state["change_log"]) == 4


def test_sync_store_applies_incremental_deletion(tmp_path: Path):
    store = SyncStore(tmp_path / "state")
    apply_sync_payload(
        store,
        {
            "sync_token": "token-1",
            "full_sync": True,
            "items": [{"id": "1", "content": "Active", "checked": False, "is_deleted": False}],
        },
    )
    apply_sync_payload(
        store,
        {
            "sync_token": "token-2",
            "full_sync": False,
            "items": [{"id": "1", "content": "Active", "checked": False, "is_deleted": True}],
        },
    )

    state = store.load_state()
    assert state["sync_token"] == "token-2"
    assert "1" not in state["resources"]["items"]
    assert state["deleted_items"]["1"]["content"] == "Active"
