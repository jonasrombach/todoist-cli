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
- `TodoistAPIAsync` is not exposed. Its resource methods match the synchronous client, plus async lifecycle handling (`close`). That is not a functional gap for one-shot CLI commands; it matters only if this repo grows a long-running daemon or webhook receiver.
- OAuth helper functions from `todoist_api_python.authentication` are not exposed. That is acceptable for personal-token local use, but webhook support needs OAuth because Todoist activates webhooks for a user only after that user completes the app's OAuth flow.
- Todoist API v1 has broader surfaces than the Python SDK wrapper: `/sync`, webhooks, dynamic client registration, OAuth metadata clients/PKCE, uploads/templates/activity/backups/email/workspace features, and the official Todoist MCP server. This CLI should not try to mirror every v1 endpoint immediately; for Hermes, the high-value gap is reliable local state and change notification.
- The current `heartbeat-context` already uses `/sync` for a full read of selected resources (`items`, `projects`, `sections`, `labels`), but it does not persist `sync_token`, maintain a reusable cache, record deletions/completions over time, or expose a general sync command.
- Webhooks reduce latency and unnecessary polling, but Todoist explicitly says webhook delivery can be delayed, out of order, or fail; webhooks must be treated as wake-up signals that trigger sync, not as the primary data source.

### Concrete implementation plan

1. **Stabilize automation-facing output.**
   - Add `--format json` error objects for failures: `{status:"error", error_type, message, request_id?, status_code?, retryable?}`.
   - Keep human-readable stderr for direct CLI use.
   - Add tests for SDK/httpx failures and malformed input.

2. **Tighten argument parsing and validation.**
   - Parse `date`, `datetime`, integer, boolean, list, and object options deliberately before calling the SDK.
   - Validate mutually exclusive or dependent fields where the SDK/API expects them, especially due/deadline/reminder/location options.
   - Keep `raw` permissive, but make friendly command aliases safer.

3. **Create a local sync store.**
   - Add a small SQLite DB or state directory under `${XDG_STATE_HOME:-~/.local/state}/todoist-cli/`.
   - Store: latest `sync_token`, full-sync timestamp, active tasks/items, projects, sections, labels, reminders, last-seen IDs, completed/deleted evidence, and a compact change log.
   - Redact or avoid unnecessary personal fields in logs; task titles are personal data.

4. **Implement a reusable incremental `/sync` client.**
   - Add `todoist-cli sync pull --resources items,projects,sections,labels,reminders`.
   - First run uses `sync_token='*'`; later runs use the persisted token.
   - Apply returned deltas to the local sync store and persist the new token atomically.
   - Fall back to a full sync if the token is rejected, missing, or the local store is corrupt.
   - Expose `sync status` and `sync reset` for inspection and recovery.

5. **Rebuild `heartbeat-context` on the sync store.**
   - Make `heartbeat-context` call incremental sync first, then build context from the local store.
   - Distinguish active, completed, deleted/unknown, postponed, overdue, today, next 7 days, and high-priority/no-near-due buckets.
   - Never infer that a disappeared active task is still open; reconcile against completed-task evidence and sync deletion markers.

6. **Add completed-task backfill.**
   - Use `get_completed_tasks_by_completion_date` and/or `get_completed_tasks_by_due_date` to backfill recent completions, especially before the first local ledger exists or after downtime.
   - Store the backfill window and make it configurable, e.g. 7–30 days.
   - Merge backfill evidence into the sync store without duplicating tasks.

7. **Add webhook ingestion as a wake-up layer.**
   - Add a minimal receiver or integration endpoint that verifies `X-Todoist-Hmac-SHA256`, accepts configured events, writes an append-only event receipt, responds `200` quickly, and debounces bursts.
   - On event receipt, trigger `sync pull`; do not trust the webhook payload alone as canonical state.
   - Subscribe at least to task events (`item:added`, `item:updated`, `item:deleted`, `item:completed`, `item:uncompleted`) plus project/section/label/reminder/comment events if those affect context.
   - Account for Todoist constraints: callback URL must be HTTPS with no explicit port; local-only/Tailscale URLs need a relay/tunnel/public webhook route.

8. **Implement OAuth/app setup for webhooks.**
   - Document or add commands for authorization URL generation, token exchange, refresh-token rotation, revocation, and secure storage.
   - Include personal-use activation: the app creator still needs to complete the OAuth flow for their own account before webhooks fire.
   - Store webhook secrets and OAuth refresh tokens outside the repo; never print token values.

9. **Optionally add `/sync` batch writes.**
   - Support command batching where it provides real value: dependent writes, fewer requests, or atomic-ish multi-step changes.
   - Handle `uuid`, `temp_id`, `temp_id_mapping`, partial command failures, and idempotent retry behavior.
   - Keep ordinary SDK commands as the default until batch-write semantics are well tested.

### Lower-priority gaps

- Custom SDK client injection is not exposed: the SDK accepts a custom `httpx.Client` and `request_id_fn`; the CLI only supports the default client/token path. This matters mainly for advanced timeout, retry, proxy, tracing, or request-ID observability needs.
- SDK model schemas and enum/value discovery are not surfaced. They would improve help text and validation, but are less important than sync correctness.
- Async CLI mode is not exposed. Keep this deferred unless a daemon/watch/webhook process becomes part of this repository.
- Non-SDK Todoist API v1 surfaces such as uploads, templates, activity, backups, email helpers, workspace/admin operations, and MCP integration are intentionally out of initial scope unless a concrete workflow needs them.
