from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MethodSpec:
    name: str
    group: str
    action: str
    positional: tuple[str, ...] = ()
    options: tuple[str, ...] = ()
    mutating: bool = False
    paginated: bool = False
    help: str = ""


METHOD_SPECS: dict[str, MethodSpec] = {
    "add_comment": MethodSpec("add_comment", "comments", "add", ("content",), ("project_id", "task_id", "attachment", "uids_to_notify"), True, help="Create a comment on a task or project."),
    "add_label": MethodSpec("add_label", "labels", "add", ("name",), ("color", "item_order", "is_favorite"), True),
    "add_location_reminder": MethodSpec("add_location_reminder", "location-reminders", "add", ("task_id", "name", "loc_lat", "loc_long", "loc_trigger"), ("radius",), True),
    "add_project": MethodSpec("add_project", "projects", "add", ("name",), ("description", "parent_id", "color", "is_favorite", "view_style"), True),
    "add_reminder": MethodSpec("add_reminder", "reminders", "add", ("task_id",), ("reminder_type", "minute_offset", "due_string", "due_date", "due_datetime", "due_lang", "due_timezone", "service"), True),
    "add_section": MethodSpec("add_section", "sections", "add", ("name", "project_id"), ("order",), True),
    "add_task": MethodSpec("add_task", "tasks", "add", ("content",), ("description", "project_id", "section_id", "parent_id", "labels", "priority", "due_string", "due_lang", "due_date", "due_datetime", "assignee_id", "duration", "duration_unit", "deadline_date", "deadline_lang"), True),
    "add_task_quick": MethodSpec("add_task_quick", "tasks", "quick-add", ("text",), ("note", "reminder", "auto_reminder"), True),
    "archive_project": MethodSpec("archive_project", "projects", "archive", ("project_id",), mutating=True),
    "complete_task": MethodSpec("complete_task", "tasks", "complete", ("task_id",), mutating=True),
    "delete_comment": MethodSpec("delete_comment", "comments", "delete", ("comment_id",), mutating=True),
    "delete_label": MethodSpec("delete_label", "labels", "delete", ("label_id",), mutating=True),
    "delete_location_reminder": MethodSpec("delete_location_reminder", "location-reminders", "delete", ("location_reminder_id",), mutating=True),
    "delete_project": MethodSpec("delete_project", "projects", "delete", ("project_id",), mutating=True),
    "delete_reminder": MethodSpec("delete_reminder", "reminders", "delete", ("reminder_id",), mutating=True),
    "delete_section": MethodSpec("delete_section", "sections", "delete", ("section_id",), mutating=True),
    "delete_task": MethodSpec("delete_task", "tasks", "delete", ("task_id",), mutating=True),
    "filter_tasks": MethodSpec("filter_tasks", "tasks", "filter", options=("query", "lang", "limit"), paginated=True),
    "get_collaborators": MethodSpec("get_collaborators", "collaborators", "list", ("project_id",), ("limit",), paginated=True),
    "get_comment": MethodSpec("get_comment", "comments", "get", ("comment_id",)),
    "get_comments": MethodSpec("get_comments", "comments", "list", options=("project_id", "task_id", "limit"), paginated=True),
    "get_completed_tasks_by_completion_date": MethodSpec("get_completed_tasks_by_completion_date", "completed", "by-completion-date", options=("since", "until", "workspace_id", "filter_query", "filter_lang", "limit"), paginated=True),
    "get_completed_tasks_by_due_date": MethodSpec("get_completed_tasks_by_due_date", "completed", "by-due-date", options=("since", "until", "workspace_id", "project_id", "section_id", "parent_id", "filter_query", "filter_lang", "limit"), paginated=True),
    "get_label": MethodSpec("get_label", "labels", "get", ("label_id",)),
    "get_labels": MethodSpec("get_labels", "labels", "list", options=("limit",), paginated=True),
    "get_location_reminder": MethodSpec("get_location_reminder", "location-reminders", "get", ("location_reminder_id",)),
    "get_location_reminders": MethodSpec("get_location_reminders", "location-reminders", "list", options=("task_id", "limit"), paginated=True),
    "get_project": MethodSpec("get_project", "projects", "get", ("project_id",)),
    "get_projects": MethodSpec("get_projects", "projects", "list", options=("limit",), paginated=True),
    "get_reminder": MethodSpec("get_reminder", "reminders", "get", ("reminder_id",)),
    "get_reminders": MethodSpec("get_reminders", "reminders", "list", options=("task_id", "limit"), paginated=True),
    "get_section": MethodSpec("get_section", "sections", "get", ("section_id",)),
    "get_sections": MethodSpec("get_sections", "sections", "list", options=("project_id", "limit"), paginated=True),
    "get_shared_labels": MethodSpec("get_shared_labels", "labels", "shared", options=("omit_personal", "limit"), paginated=True),
    "get_task": MethodSpec("get_task", "tasks", "get", ("task_id",)),
    "get_tasks": MethodSpec("get_tasks", "tasks", "list", options=("project_id", "section_id", "parent_id", "label", "ids", "limit"), paginated=True),
    "move_task": MethodSpec("move_task", "tasks", "move", ("task_id",), ("project_id", "section_id", "parent_id"), True),
    "remove_shared_label": MethodSpec("remove_shared_label", "labels", "remove-shared", ("name",), mutating=True),
    "rename_shared_label": MethodSpec("rename_shared_label", "labels", "rename-shared", ("name", "new_name"), mutating=True),
    "search_labels": MethodSpec("search_labels", "labels", "search", ("query",), ("limit",), paginated=True),
    "search_projects": MethodSpec("search_projects", "projects", "search", ("query",), ("limit",), paginated=True),
    "search_sections": MethodSpec("search_sections", "sections", "search", ("query",), ("project_id", "limit"), paginated=True),
    "unarchive_project": MethodSpec("unarchive_project", "projects", "unarchive", ("project_id",), mutating=True),
    "uncomplete_task": MethodSpec("uncomplete_task", "tasks", "uncomplete", ("task_id",), mutating=True),
    "update_comment": MethodSpec("update_comment", "comments", "update", ("comment_id", "content"), mutating=True),
    "update_label": MethodSpec("update_label", "labels", "update", ("label_id",), ("name", "color", "item_order", "is_favorite"), True),
    "update_location_reminder": MethodSpec("update_location_reminder", "location-reminders", "update", ("location_reminder_id",), ("name", "loc_lat", "loc_long", "loc_trigger", "radius"), True),
    "update_project": MethodSpec("update_project", "projects", "update", ("project_id",), ("name", "description", "color", "is_favorite", "view_style", "order", "collapsed"), True),
    "update_reminder": MethodSpec("update_reminder", "reminders", "update", ("reminder_id",), ("minute_offset", "due_string", "due_date", "due_datetime", "due_lang", "due_timezone", "service"), True),
    "update_section": MethodSpec("update_section", "sections", "update", ("section_id",), ("name", "order", "collapsed"), True),
    "update_task": MethodSpec("update_task", "tasks", "update", ("task_id",), ("content", "description", "labels", "priority", "due_string", "due_lang", "due_date", "due_datetime", "assignee_id", "duration", "duration_unit", "deadline_date", "deadline_lang"), True),
}


def iter_specs() -> list[MethodSpec]:
    return sorted(METHOD_SPECS.values(), key=lambda s: (s.group, s.action, s.name))
