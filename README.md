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

The synchronous `TodoistAPI` SDK surface is covered, and the first automation-reliability slice is implemented: structured JSON errors, typed option coercion, local sync state, incremental `/sync pull`, `heartbeat-context` on the sync store, completed-task backfill by completion date, webhook HMAC receipt handling, and OAuth authorization URL generation.

Remaining work:

1. **Harden structured errors.**
   - Add optional `request_id`, `status_code`, and `retryable` fields for Todoist SDK/API failures where available.
   - Preserve the current compact JSON contract for automation callers.

2. **Finish friendly-command validation.**
   - Validate mutually exclusive or dependent fields before SDK calls, especially due/deadline/reminder/location options.
   - Keep `raw` permissive, but make human-friendly aliases fail early with clear errors.

3. **Make sync recovery robust.**
   - Fall back to a full sync when Todoist rejects a stored `sync_token`, the token is missing, or local state is corrupt.
   - Add explicit corruption detection/recovery tests.
   - Decide whether the current JSON state file is enough or whether SQLite is worth it once the ledger grows.

4. **Improve `heartbeat-context` semantics.**
   - Distinguish active, completed, deleted/unknown, postponed, overdue, today, next 7 days, and high-priority/no-near-due buckets as first-class output, not just counts for completed/deleted evidence.
   - Avoid treating disappeared active tasks as open unless completion/deletion evidence supports it.
   - Optionally run completed-task backfill before heartbeat generation after downtime or first setup.

5. **Complete completed-task backfill.**
   - Add backfill by due date via `get_completed_tasks_by_due_date` where useful.
   - Store and expose backfill windows per strategy without duplicating tasks.

6. **Turn webhook handling into an operational endpoint.**
   - The current CLI can verify a Todoist HMAC payload, write a redacted receipt, and trigger sync. Still needed: an actual receiver/integration endpoint that responds `200` quickly.
   - Add event filtering and debouncing for bursts.
   - Subscribe at least to task events (`item:added`, `item:updated`, `item:deleted`, `item:completed`, `item:uncompleted`) plus project/section/label/reminder/comment events if those affect context.
   - Account for Todoist constraints: callback URL must be HTTPS with no explicit port; local-only/Tailscale URLs need a relay, tunnel, or public webhook route.

7. **Complete OAuth/app setup for webhooks.**
   - The CLI can generate an authorization URL. Still needed: token exchange, refresh-token rotation, revocation, secure token storage, and clear personal-use activation docs.
   - Store webhook secrets and OAuth refresh tokens outside the repo; never print token values.

8. **Optionally add `/sync` batch writes.**
   - Support command batching where it provides real value: dependent writes, fewer requests, or atomic-ish multi-step changes.
   - Handle `uuid`, `temp_id`, `temp_id_mapping`, partial command failures, and idempotent retry behavior.
   - Keep ordinary SDK commands as the default until batch-write semantics are well tested.

### Lower-priority gaps

- Custom SDK client injection is not exposed: the SDK accepts a custom `httpx.Client` and `request_id_fn`; the CLI only supports the default client/token path. This matters mainly for advanced timeout, retry, proxy, tracing, or request-ID observability needs.
- SDK model schemas and enum/value discovery are not surfaced. They would improve help text and validation, but are less important than sync correctness.
- Async CLI mode is not exposed. Keep this deferred unless a daemon/watch/webhook process becomes part of this repository.
- Non-SDK Todoist API v1 surfaces such as uploads, templates, activity, backups, email helpers, workspace/admin operations, and MCP integration are intentionally out of initial scope unless a concrete workflow needs them.
