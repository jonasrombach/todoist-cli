
from todoist_cli.context import build_heartbeat_context


def test_heartbeat_context_buckets_tasks():
    payload = {
        "projects": [{"id": "p1", "name": "Admin"}],
        "sections": [],
        "labels": [{"id": "l1", "name": "phone"}],
        "items": [
            {"id": "1", "content": "Late", "project_id": "p1", "priority": 1, "labels": ["l1"], "due": {"date": "2026-05-03"}},
            {"id": "2", "content": "Today", "project_id": "p1", "priority": 4, "labels": [], "due": {"date": "2026-05-04"}},
            {"id": "3", "content": "Soon", "project_id": "p1", "priority": 2, "labels": [], "due": {"date": "2026-05-08"}},
            {"id": "4", "content": "Important", "project_id": "p1", "priority": 4, "labels": [], "due": None},
        ],
    }

    ctx = build_heartbeat_context(payload, now_iso="2026-05-04T09:00:00+02:00")

    assert [t["content"] for t in ctx["tasks"]["overdue"]] == ["Late"]
    assert [t["content"] for t in ctx["tasks"]["today"]] == ["Today"]
    assert [t["content"] for t in ctx["tasks"]["next_7_days"]] == ["Soon"]
    assert [t["content"] for t in ctx["tasks"]["high_priority_no_near_due"]] == ["Important"]
