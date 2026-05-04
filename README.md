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

### Review findings

- Current SDK coverage is complete for the installed synchronous Python SDK: 51/51 public `TodoistAPI` methods are exposed, and the CLI specs match the current method parameters.
- `TodoistAPIAsync` is not exposed. Its resource methods match the synchronous client, plus async lifecycle handling (`close`). That is not a functional gap for a CLI unless a long-running daemon is added.
- The Todoist API v1 `/sync` endpoint is already used by `heartbeat-context` for a full read of selected resources, but there is no reusable sync client, persisted `sync_token`, incremental cache, or command-batch writer yet.
- Webhooks are separate from `/sync`: they can wake automation in near-real time, but they should trigger an incremental sync rather than replace local state reconciliation.

### Recommended implementation order

1. **Structured errors and safer output contracts.** Return machine-readable error JSON for SDK/httpx failures while keeping stderr human-readable. This makes automation less brittle and is low-risk.
2. **Type-aware argument parsing and validation.** Parse `date`/`datetime`/list/object parameters intentionally, expose useful validation errors, and keep JSON options predictable. This improves every mutating command before adding more automation.
3. **Local sync ledger for task reconciliation.** Store a compact local state file or SQLite DB with last-seen task IDs, project/section/label names, completion/deletion evidence, and a timestamped change log. This prevents automation from treating disappeared active tasks as mysterious or still-open.
4. **Incremental `/sync` client.** Replace repeated full reads with `sync_token`-based incremental sync against `https://api.todoist.com/api/v1/sync`, with configurable `resource_types` and fallback to `sync_token='*'` when local state is missing or invalid.
5. **Completed-task backfill.** Use `get_completed_tasks_by_completion_date` / `get_completed_tasks_by_due_date` to reconcile recent completions, especially for tasks completed in Todoist native apps before the local ledger saw the change.
6. **Webhook-triggered refresh.** Add a small webhook receiver that verifies `X-Todoist-Hmac-SHA256`, accepts subscribed events (`item:added`, `item:updated`, `item:deleted`, `item:completed`, `item:uncompleted`, and related project/section/label events), debounces bursts, then runs incremental sync. Webhooks reduce polling latency and request volume, but they need a public HTTPS callback with no explicit port; local-only/Tailscale URLs are not enough without a relay/tunnel.
7. **OAuth/app setup for webhooks.** Personal API tokens are enough for local CLI reads/writes, but webhooks are configured through a Todoist app/integration. Supporting them cleanly means documenting or implementing app registration/OAuth, callback URL setup, subscribed events, webhook secret storage, and token refresh/revocation handling.
8. **Batch writes via `/sync` commands.** Add optional command batching for operations that benefit from atomic/dependent writes and `temp_id` mapping. Keep ordinary SDK commands as the default until batch semantics are tested.

### Lower-priority gaps

- OAuth helper commands are not exposed: `get_authentication_url`, `get_auth_token`, `revoke_auth_token`, and async variants from `todoist_api_python.authentication` are not implemented as CLI commands. Add these only when supporting multi-user auth or webhooks; personal-token local use does not need them.
- Custom SDK client injection is not exposed: the SDK accepts a custom `httpx.Client` and `request_id_fn`; the CLI only supports the default client/token path. This matters mainly for advanced timeout, retry, proxy, or observability needs.
- Model-level docs are not surfaced: SDK model objects and constraints are serialized after the fact, but the CLI does not yet provide model schemas or enum/value discovery commands.
- Async CLI mode is not exposed. Keep this deferred unless the repo grows a daemon/watch process where async HTTP lifecycle management would matter.
