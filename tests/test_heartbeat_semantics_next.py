from todoist_cli.context import build_heartbeat_context


def test_heartbeat_context_exposes_completed_deleted_unknown_and_postponed_buckets():
    payload = {
        "items": [
            {"id": "1", "content": "Active", "priority": 1, "due": {"date": "2026-05-04"}},
            {"id": "2", "content": "Later", "priority": 1, "due": {"date": "2026-05-20"}},
        ],
        "completed_items": {
            "3": {
                "id": "3",
                "content": "Done",
                "checked": True,
                "completed_at": "2026-05-04T10:00:00Z",
                "completed_by_uid": "u1",
            }
        },
        "deleted_items": {"4": {"id": "4", "content": "Deleted", "is_deleted": True}},
    }

    ctx = build_heartbeat_context(payload, now_iso="2026-05-04T09:00:00+02:00")

    assert [t["content"] for t in ctx["tasks"]["today"]] == ["Active"]
    assert [t["content"] for t in ctx["tasks"]["postponed"]] == ["Later"]
    assert [t["content"] for t in ctx["tasks"]["completed"]] == ["Done"]
    assert ctx["tasks"]["completed"][0]["evidence"] == {
        "kind": "todoist_completed_item",
        "task_id": "3",
        "checked": True,
        "completed_at": "2026-05-04T10:00:00Z",
        "completed_by_uid": "u1",
    }
    assert [t["content"] for t in ctx["tasks"]["deleted_unknown"]] == ["Deleted"]
    assert ctx["tasks"]["deleted_unknown"][0]["evidence"] == {
        "kind": "todoist_deleted_item",
        "task_id": "4",
        "is_deleted": True,
    }
    assert "postponed" in ctx["bucket_order"]
    assert ctx["counts"]["completed"] == 1
    assert ctx["counts"]["deleted_unknown"] == 1
