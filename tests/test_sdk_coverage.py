import inspect

from todoist_api_python.api import TodoistAPI

from todoist_cli.sdk import METHOD_SPECS


def test_all_public_sync_sdk_methods_are_exposed():
    sdk_methods = {
        name
        for name, obj in inspect.getmembers(TodoistAPI, predicate=inspect.isfunction)
        if not name.startswith("_")
    }

    assert set(METHOD_SPECS) == sdk_methods


def test_all_public_sync_sdk_method_parameters_are_exposed():
    missing: dict[str, set[str]] = {}
    for name, obj in inspect.getmembers(TodoistAPI, predicate=inspect.isfunction):
        if name.startswith("_"):
            continue
        params = set(inspect.signature(obj).parameters) - {"self"}
        spec = METHOD_SPECS[name]
        covered = set(spec.positional) | set(spec.options)
        diff = params - covered
        if diff:
            missing[name] = diff

    assert missing == {}
