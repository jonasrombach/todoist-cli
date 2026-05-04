from pathlib import Path

from todoist_cli.sync_store import SyncStore, apply_completed_backfill


def test_completed_backfill_records_completed_items_without_duplicates(tmp_path: Path):
    store = SyncStore(tmp_path / "state")

    state = apply_completed_backfill(
        store,
        [
            {"id": "c1", "task_id": "1", "content": "Done once", "completed_at": "2026-05-04T08:00:00Z"},
            {"id": "c1", "task_id": "1", "content": "Done once", "completed_at": "2026-05-04T08:00:00Z"},
        ],
        window_days=14,
    )

    assert state["completed_backfill"]["window_days"] == 14
    assert state["completed_backfill"]["items"]["1"]["content"] == "Done once"
    assert len(state["completed_backfill"]["items"]) == 1
