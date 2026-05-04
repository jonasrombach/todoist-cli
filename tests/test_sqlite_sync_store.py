import json
import sqlite3
from pathlib import Path

from todoist_cli.cli import main
from todoist_cli.sync_store import SyncStore, apply_completed_backfill, apply_sync_payload


def test_sqlite_store_persists_sync_state(tmp_path: Path):
    store = SyncStore(tmp_path, backend="sqlite")
    apply_sync_payload(
        store,
        {
            "sync_token": "token-1",
            "full_sync": True,
            "items": [
                {"id": "1", "content": "Active", "checked": False, "is_deleted": False},
                {"id": "2", "content": "Done", "checked": True, "is_deleted": False},
            ],
            "projects": [{"id": "p1", "name": "Inbox"}],
        },
    )

    state = SyncStore(tmp_path, backend="sqlite").load_state()
    assert state["sync_token"] == "token-1"
    assert state["resources"]["items"]["1"]["content"] == "Active"
    assert state["completed_items"]["2"]["content"] == "Done"
    assert state["resources"]["projects"]["p1"]["name"] == "Inbox"
    assert (tmp_path / "sync-state.sqlite3").exists()


def test_sqlite_store_preserves_completed_backfill_strategies(tmp_path: Path):
    store = SyncStore(tmp_path, backend="sqlite")
    apply_completed_backfill(store, [{"task_id": "1", "content": "Done"}], window_days=7, strategy="due-date")

    state = SyncStore(tmp_path, backend="sqlite").load_state()
    assert state["completed_backfill"]["items"]["1"]["content"] == "Done"
    assert state["completed_backfill"]["strategies"]["due-date"]["items"]["1"]["content"] == "Done"
    assert state["completed_items"]["1"]["content"] == "Done"


def test_sqlite_store_recovers_from_corrupt_database(tmp_path: Path):
    (tmp_path / "sync-state.sqlite3").write_text("not sqlite", encoding="utf-8")
    store = SyncStore(tmp_path, backend="sqlite")

    state = store.load_state()

    assert store.corrupt_state_recovered is True
    assert state["sync_token"] is None


def test_sync_migrate_moves_json_state_to_sqlite(tmp_path: Path, capsys):
    (tmp_path / "sync-state.json").write_text(
        json.dumps(
            {
                "sync_token": "json-token",
                "resources": {"items": {"1": {"id": "1", "content": "From JSON"}}},
                "completed_items": {},
                "deleted_items": {},
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["sync", "migrate", "--state-dir", str(tmp_path), "--remove-json"])

    assert exit_code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "migrated"
    assert out["state_backend"] == "sqlite"
    assert out["sync_token_present"] is True
    assert not (tmp_path / "sync-state.json").exists()
    assert sqlite3.connect(tmp_path / "sync-state.sqlite3").execute("SELECT value FROM meta WHERE key='sync_token'").fetchone()[0] == "json-token"


def test_sync_status_can_select_json_or_sqlite_backend(tmp_path: Path, capsys):
    json_store = SyncStore(tmp_path, backend="json")
    sqlite_store = SyncStore(tmp_path, backend="sqlite")
    apply_sync_payload(json_store, {"sync_token": "json-token", "full_sync": True, "items": []})
    apply_sync_payload(sqlite_store, {"sync_token": "sqlite-token", "full_sync": True, "items": []})

    main(["sync", "status", "--state-dir", str(tmp_path), "--state-backend", "json"])
    main(["sync", "status", "--state-dir", str(tmp_path), "--state-backend", "sqlite"])

    first, second = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert first["state_backend"] == "json"
    assert second["state_backend"] == "sqlite"
    assert first["state_file"].endswith("sync-state.json")
    assert second["state_file"].endswith("sync-state.sqlite3")
