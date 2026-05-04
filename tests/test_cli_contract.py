import json

from todoist_cli.cli import build_parser, main
from todoist_cli.sdk import METHOD_SPECS


def test_every_sdk_method_has_a_cli_spec():
    expected = {
        "add_comment", "add_label", "add_location_reminder", "add_project", "add_reminder",
        "add_section", "add_task", "add_task_quick", "archive_project", "complete_task",
        "delete_comment", "delete_label", "delete_location_reminder", "delete_project",
        "delete_reminder", "delete_section", "delete_task", "filter_tasks", "get_collaborators",
        "get_comment", "get_comments", "get_completed_tasks_by_completion_date",
        "get_completed_tasks_by_due_date", "get_label", "get_labels", "get_location_reminder",
        "get_location_reminders", "get_project", "get_projects", "get_reminder", "get_reminders",
        "get_section", "get_sections", "get_shared_labels", "get_task", "get_tasks", "move_task",
        "remove_shared_label", "rename_shared_label", "search_labels", "search_projects",
        "search_sections", "unarchive_project", "uncomplete_task", "update_comment",
        "update_label", "update_location_reminder", "update_project", "update_reminder",
        "update_section", "update_task",
    }

    assert set(METHOD_SPECS) == expected


def test_parser_exposes_human_friendly_task_aliases():
    parser = build_parser()

    args = parser.parse_args(["tasks", "add", "Buy milk", "--due-string", "tomorrow"])

    assert args.sdk_method == "add_task"
    assert args.content == "Buy milk"
    assert args.due_string == "tomorrow"


def test_main_outputs_json_for_mocked_client(capsys):
    class FakeClient:
        def get_projects(self, limit=None):
            assert limit == 10
            return [[{"id": "1", "name": "Inbox"}]]

    exit_code = main(["projects", "list", "--limit", "10"], client_factory=lambda: FakeClient())

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == [{"id": "1", "name": "Inbox"}]
