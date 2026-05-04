# todoist-cli

A complete command-line wrapper around the official Todoist Python SDK.

Status: initial implementation.

## Install

```bash
pip install -e .
```

Set a token:

```bash
export TODOIST_API_TOKEN="..."
```

or put it in `~/.hermes/.env`:

```text
TODOIST_API_TOKEN=...
```

## Examples

```bash
todoist-cli projects list
todoist-cli tasks list --limit 20
todoist-cli tasks add "Buy milk" --due-string tomorrow
todoist-cli task get <task_id>
todoist-cli labels list
todoist-cli raw get_tasks --limit 5
todoist-cli heartbeat-context
```

By default output is JSON. Mutating operations require `--yes` unless `TODOIST_CLI_ASSUME_YES=1` is set.
