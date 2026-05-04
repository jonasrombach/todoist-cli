import json
from pathlib import Path

from todoist_cli.cli import main


def test_sync_pull_falls_back_to_full_sync_when_incremental_token_rejected(tmp_path: Path, capsys):
    state_file = tmp_path / "sync-state.json"
    state_file.write_text(json.dumps({"sync_token": "bad", "resources": {}}), encoding="utf-8")
    calls = []

    def fake_fetch(token=None, sync_token="*", resource_types=None):
        calls.append(sync_token)
        if sync_token == "bad":
            exc = RuntimeError("Invalid sync token")
            exc.status_code = 400
            raise exc
        return {"sync_token": "fresh", "full_sync": True, "items": [{"id": "1", "content": "Recovered"}]}

    exit_code = main(["sync", "pull", "--state-dir", str(tmp_path)], sync_fetcher=fake_fetch)

    assert exit_code == 0
    assert calls == ["bad", "*"]
    out = json.loads(capsys.readouterr().out)
    assert out["sync_token_present"] is True
    assert out["counts"]["items"] == 1


def test_sync_status_recovers_from_corrupt_state_file(tmp_path: Path, capsys):
    (tmp_path / "sync-state.json").write_text("not-json", encoding="utf-8")

    exit_code = main(["sync", "status", "--state-dir", str(tmp_path)])

    assert exit_code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["corrupt_state_recovered"] is True
    assert out["sync_token_present"] is False
