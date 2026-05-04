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

## Missing / roadmap

The synchronous `TodoistAPI` SDK surface is covered. Automation reliability work is implemented: structured JSON errors with retry metadata where available, typed option coercion, friendly-command validation, local sync state with incremental `/sync pull` and full-sync recovery, `heartbeat-context` on the sync store, completed-task backfill by completion date and due date, webhook HMAC receipt handling plus a minimal operational receiver, OAuth helper/storage primitives, model/spec discovery, and `/sync` batch payload helpers.

No high-priority functional roadmap items remain for the current Hermes/Todoist workflow.

### Deferred / optional gaps

- **Production webhook deployment.** The repo now has the receiver primitive, filtering, debouncing, and sync trigger hook. Actual deployment still depends on infrastructure choice: public HTTPS callback with no explicit port, relay, tunnel, or Hermes webhook gateway route.
- **OAuth live exchange wiring.** The repo has request builders and secure token storage primitives. A real app still needs client credentials, callback hosting, and account activation through Todoist's OAuth flow before webhooks fire.
- **SQLite migration.** Current JSON state is adequate for the small local ledger. Revisit SQLite only if state grows enough to need querying, locking, or multi-process writes.
- **Broad Todoist API v1 expansion.** Uploads, templates, activity, backups, email helpers, workspace/admin operations, and MCP integration remain intentionally out of scope unless a concrete workflow needs them.
- **Async CLI mode and custom SDK client injection.** Keep deferred unless this repo grows a long-running daemon or needs advanced timeout/proxy/tracing behavior.
