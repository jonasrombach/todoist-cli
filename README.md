# todoist-cli

A command-line wrapper around the official Todoist Python SDK.

The CLI exposes the synchronous `TodoistAPI` surface as shell commands with JSON output, plus a compact task-context command for automation agents and personal dashboards.

## Install

```bash
pip install -e .
```

## Authentication

Set a Todoist API token in your shell:

```bash
export TODOIST_API_TOKEN="***"
```

Or put it in a local dotenv-style file and point the CLI at it:

```bash
export TODOIST_CLI_ENV_FILE="$HOME/.config/todoist-cli/env"
```

Example env file:

```text
TODOIST_API_TOKEN=***
```

For backwards compatibility, the CLI also checks `~/.hermes/.env` when `TODOIST_CLI_ENV_FILE` is not set. That fallback is intended for local automation setups; do not commit real dotenv files.

## Examples

```bash
todoist-cli projects list
todoist-cli tasks list --limit 20
todoist-cli tasks add "Buy milk" --due-string tomorrow
todoist-cli tasks get <task_id>
todoist-cli labels list
todoist-cli raw get_tasks --limit 5
todoist-cli heartbeat-context
```

By default output is compact JSON. Use `--format pretty` for indented JSON.

The CLI is intentionally implementation-agnostic and does not add agent-specific confirmation gates. Callers and automation agents must apply their own safety policy before invoking mutating commands such as `add`, `update`, `move`, `complete`, `archive`, or `delete`.

## Security and privacy

- Never commit real Todoist tokens, `.env` files, API responses, task exports, or logs containing personal task contents.
- Prefer `TODOIST_CLI_ENV_FILE` for local dotenv paths instead of documenting machine-specific paths in shared automation.
- Treat `heartbeat-context` output as personal data. It can include task titles, due dates, labels, project names, and task URLs.
- Public repositories should keep examples generic and avoid embedding personal workflows, private project names, addresses, contacts, or task contents.

## SDK coverage

Implemented for the synchronous `TodoistAPI` client:

- 51/51 public `TodoistAPI` methods exposed.
- All current public method parameters from the installed SDK are represented in the CLI specs.
- Resource groups covered: tasks, projects, sections, labels, shared labels, reminders, location reminders, comments, collaborators, completed tasks.
- Paginated SDK iterators are flattened to JSON arrays by default.
- `raw` exposes exact SDK method names for less common operations.

## Automation features

Beyond the SDK wrapper, the repo now includes the local automation layer Hermes needs:

- Structured JSON errors, including `status_code`, `request_id`, and `retryable` where the SDK/API exposes them.
- Typed option coercion for dates, datetimes, numbers, booleans, and JSON options, plus validation for common dangerous/friendly-command combinations.
- Incremental `/sync` state under `${XDG_STATE_HOME:-~/.local/state}/todoist-cli/sync-state.json`, with full-sync recovery for rejected tokens and corrupt local state.
- `heartbeat-context` built from the local sync store with semantic buckets for overdue, today, next-7-days, postponed, high-priority unscheduled, completed, and deleted evidence.
- Completed-task backfill by completion date and due date.
- Todoist webhook HMAC verification, privacy-preserving receipt logging, and a minimal HTTP receiver via `todoist-cli webhook serve`.
- OAuth helper flow: authorization URL, token exchange, token refresh, secure local token storage with `0600`, and redacted output.
- `todoist-cli models list` for method/spec discovery.
- `/sync` batch payload helper primitives in the Python package for dependent writes.

## Operational notes

No high-priority functional roadmap items remain for the current Hermes/Todoist workflow.

Things intentionally not built until there is a concrete need:

- Production webhook hosting/relay choice. Todoist requires a public HTTPS callback without an explicit port; this depends on deployment infrastructure, not the CLI package itself.
- SQLite state storage. JSON is adequate for the current small local ledger.
- Broad non-SDK Todoist API v1 expansion such as uploads, templates, activity, backups, email helpers, workspace/admin operations, or MCP integration.
- Async CLI mode and custom SDK client injection, unless this grows into a long-running daemon or needs advanced timeout/proxy/tracing behavior.
