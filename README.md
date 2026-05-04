# todoist-cli

A JSON-first command-line wrapper around the official Todoist Python SDK.

`todoist-cli` exposes the synchronous `TodoistAPI` surface as shell commands, plus a local automation layer for incremental sync, heartbeat/task context, webhooks, and OAuth helpers. It is designed to work for humans in a terminal and for automation agents such as OpenClaw, Claude Code, Codex, Cursor, or shell scripts.

## Install

Requirements:

- Python 3.10+
- A Python build with the standard-library `sqlite3` module
- A Todoist API token for personal/local use, or Todoist OAuth app credentials for third-party/webhook use

From this repository:

```bash
python3 -m pip install .
```

For isolated CLI installation from GitHub:

```bash
pipx install 'git+https://github.com/jonasrombach/todoist-cli.git'
# or
uv tool install 'git+https://github.com/jonasrombach/todoist-cli.git'
```

For development:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
```

## Authentication

For personal/local use, set a Todoist API token in the environment:

```bash
export TODOIST_API_TOKEN="***"
```

`TODOIST_TOKEN` is also accepted as a legacy alias.

For a dotenv-style local file, prefer the neutral config path:

```bash
mkdir -p "$HOME/.config/todoist-cli"
printf 'TODOIST_API_TOKEN=***\n' > "$HOME/.config/todoist-cli/env"
chmod 600 "$HOME/.config/todoist-cli/env"
```

Or point to any explicit dotenv file:

```bash
export TODOIST_CLI_ENV_FILE="$HOME/.config/todoist-cli/env"
```

Credential lookup order:

1. `TODOIST_API_TOKEN`
2. `TODOIST_TOKEN`
3. `TODOIST_CLI_ENV_FILE`, if set
4. `$HOME/.config/todoist-cli/env`

Never commit real tokens or local dotenv files.

## Quick examples

```bash
todoist-cli projects list
todoist-cli tasks list --limit 20
todoist-cli tasks add "Buy milk" --due-string tomorrow --priority P2
todoist-cli tasks get <task_id>
todoist-cli labels list
todoist-cli raw get_tasks --limit 5
todoist-cli heartbeat-context
```

By default, output is compact JSON. Use `--format pretty` for indented JSON:

```bash
todoist-cli --format pretty tasks list --limit 5
```

The CLI accepts Todoist UI priority names as well as raw API numbers:

- `--priority P1` maps to API priority `4`.
- `--priority P2` maps to API priority `3`.
- `--priority P3` maps to API priority `2`.
- `--priority P4`, `normal`, or `none` maps to API priority `1`.

Raw numeric `--priority 1..4` is still accepted for SDK/API parity.

## Agent and automation contract

`todoist-cli` is intended to be safe to call from shell scripts and agent runtimes.

- stdout contains the command result as JSON.
- stderr is reserved for human-readable diagnostics and errors.
- Exit code `0` means success.
- Non-zero exit means failure.
- Global flags such as `--format` must come before the subcommand.
- Mutating commands do not ask for confirmation; callers and agents must apply their own safety policy before invoking actions such as `add`, `update`, `move`, `complete`, `archive`, or `delete`.
- Error output on stdout is a structured JSON envelope:

```json
{"status":"error","error_type":"ValueError","message":"..."}
```

When available, errors also include:

```json
{"status_code":429,"request_id":"...","retryable":true}
```

Useful patterns:

```bash
todoist-cli tasks list --limit 5 | jq .
todoist-cli --format pretty sync status
todoist-cli heartbeat-context --no-sync | jq '.tasks.today'
```

## State and privacy

The sync store contains personal Todoist data such as task titles, due dates, project IDs/names, labels, URLs, completed-task evidence, deleted-task evidence, and a compact local change log.

Default state location:

```text
${XDG_STATE_HOME:-~/.local/state}/todoist-cli/
```

Files:

- `sync-state.sqlite3` — default local sync state database.
- `sync-state.json` — legacy/optional JSON backend state.
- `oauth-tokens.json` — OAuth tokens written with mode `0600`.
- `webhook-receipts.jsonl` — privacy-preserving webhook receipts; raw `event_data` is intentionally not stored.

Choose a custom state directory:

```bash
todoist-cli sync status --state-dir /path/to/state
```

Choose a state backend:

```bash
todoist-cli sync status --state-backend sqlite
todoist-cli sync status --state-backend json
export TODOIST_CLI_STATE_BACKEND=sqlite
```

Migrate legacy JSON state into SQLite:

```bash
todoist-cli sync migrate
todoist-cli sync migrate --remove-json
```

Reset local sync state:

```bash
todoist-cli sync reset
```

`sync reset` removes local state only. It does not delete Todoist tasks.

## Sync and heartbeat context

Bootstrap or update local state:

```bash
todoist-cli sync pull
todoist-cli sync status
```

Force a full sync:

```bash
todoist-cli sync pull --full
```

Backfill completed-task evidence:

```bash
todoist-cli sync backfill-completed --strategy completion-date --window-days 14
todoist-cli sync backfill-completed --strategy due-date --window-days 14
```

Build compact task context from the local store:

```bash
todoist-cli heartbeat-context
todoist-cli heartbeat-context --no-sync
```

Heartbeat buckets include:

- `overdue`
- `today`
- `next_7_days`
- `postponed`
- `high_priority_no_near_due`
- `completed`
- `deleted_unknown`

## OAuth and webhooks

Personal API tokens are enough for local CLI use. Todoist webhooks require a Todoist app and user OAuth activation.

OAuth helper flow:

```bash
todoist-cli oauth authorize-url \
  --client-id <client_id> \
  --redirect-uri https://example.com/todoist/callback \
  --scope data:read_write \
  --state <random_csrf_state>

todoist-cli oauth exchange-token \
  --client-id <client_id> \
  --client-secret <client_secret> \
  --code <code_from_redirect> \
  --redirect-uri https://example.com/todoist/callback

todoist-cli oauth refresh-token \
  --client-id <client_id> \
  --client-secret <client_secret>
```

Webhook receiver:

```bash
todoist-cli webhook serve \
  --secret <webhook_secret> \
  --host 127.0.0.1 \
  --port 8080 \
  --allow-event item:added \
  --allow-event item:updated
```

Todoist requires webhook callback URLs to use public HTTPS and no explicit port. For a local machine, use a reverse proxy, tunnel, or relay. Webhooks are wake-up signals, not canonical state: the receiver verifies `X-Todoist-Hmac-SHA256`, records a receipt, debounces events, then triggers incremental `/sync`.

## Command reference

Top-level commands:

- `tasks` — task operations.
- `projects` — project operations.
- `sections` — section operations.
- `labels` — personal label operations.
- `shared-labels` — shared label operations.
- `reminders` — reminder operations.
- `location-reminders` — location reminder operations.
- `comments` — task/project comments.
- `collaborators` — project collaborators.
- `completed` — completed-task endpoints.
- `raw` — call an exact SDK method by name.
- `sync` — local sync state commands.
- `heartbeat-context` — compact automation context from Todoist state.
- `webhook` — webhook receipt/server commands.
- `oauth` — OAuth helper commands.
- `models` — inspect known method specs.

Discover exact flags locally:

```bash
todoist-cli --help
todoist-cli tasks --help
todoist-cli tasks add --help
todoist-cli sync --help
todoist-cli webhook --help
todoist-cli oauth --help
todoist-cli models list | jq '.methods.add_task'
```

For uncommon SDK operations:

```bash
todoist-cli raw get_tasks --limit 20
todoist-cli raw call get_task <task_id>
todoist-cli raw call update_task <task_id> --kwargs '{"content":"New title"}'
```

## SDK coverage

Implemented for the synchronous `TodoistAPI` client:

- 51/51 public `TodoistAPI` methods exposed.
- All current public method parameters from the installed SDK are represented in the CLI specs.
- Resource groups covered: tasks, projects, sections, labels, shared labels, reminders, location reminders, comments, collaborators, completed tasks.
- Paginated SDK iterators are flattened to JSON arrays by default.
- `raw` exposes exact SDK method names for less common operations.

## Todoist API scope and plan limits

This project is currently an SDK wrapper plus local sync/automation layer.

Todoist API v1 includes additional surfaces that may not be first-class CLI commands here yet, including uploads, templates, backups, activity logs, workspace/admin features, dynamic client registration, MCP, and broader `/sync` write flows. Some Todoist features also depend on the authenticated user's plan or workspace permissions, especially reminders, comments, backups, uploads, filters, templates, and activity logs.

When a feature is unavailable, expect Todoist/SDK errors to be returned through the structured error contract.

## Security and privacy

- Never commit real Todoist tokens, `.env` files, OAuth token stores, API responses, task exports, sync databases, or logs containing personal task contents.
- Treat `heartbeat-context`, `sync-state.sqlite3`, and `oauth-tokens.json` as personal data.
- Public examples should stay generic and avoid private project names, addresses, contacts, or task contents.
- Webhook receipts intentionally omit raw Todoist payloads.

## Development

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
pytest -q
ruff check .
```

SDK coverage test:

```bash
pytest -q tests/test_sdk_coverage.py
```

Release checklist:

```bash
pytest -q
ruff check .
python -m compileall -q src tests
python -m build
python -m twine check dist/*
```

## Future scope

Not required for the first public release, but plausible future work:

- Publish to PyPI.
- Generate static command-reference docs from argparse/model specs.
- Add shell completion.
- Add platform-native state directories for Windows/macOS if XDG paths are not enough.
- Add first-class non-SDK Todoist API v1 commands where real workflows need them.
- Add async/custom client mode if this grows into a daemon or needs advanced timeout/proxy/tracing behavior.
- Add production webhook deployment recipes for common hosts/tunnels/relays.
