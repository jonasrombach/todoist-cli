import json

from todoist_cli.cli import main


def test_models_list_outputs_known_sdk_specs(capsys):
    exit_code = main(["models", "list"])

    assert exit_code == 0
    out = json.loads(capsys.readouterr().out)
    assert "add_task" in out["methods"]
    assert "due_string" in out["methods"]["add_task"]["options"]
