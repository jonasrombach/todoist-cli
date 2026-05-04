# todoist-cli

A command-line wrapper around the official Todoist Python SDK.

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
todoist-cli tasks get <task_id>
todoist-cli labels list
todoist-cli raw get_tasks --limit 5
todoist-cli heartbeat-context
```

By default output is JSON. The CLI is intentionally implementation-agnostic and does not add agent-specific confirmation gates; callers/agents should apply their own safety policy before invoking mutating commands.

## SDK coverage

Implemented for the synchronous `TodoistAPI` client:

- 51/51 public `TodoistAPI` methods exposed.
- All current public method parameters from the installed SDK are represented in the CLI specs.
- Resource groups covered: tasks, projects, sections, labels, shared labels, reminders, location reminders, comments, collaborators, completed tasks.
- Paginated SDK iterators are flattened to JSON arrays by default.
- `raw` exposes exact SDK method names for less common operations.

## Missing

### SDK/API surface

- Async client is not exposed: `TodoistAPIAsync` has matching resource methods plus async lifecycle handling, but this CLI currently wraps only sync `TodoistAPI`.
- OAuth helpers are not exposed: `get_authentication_url`, `get_auth_token`, `revoke_auth_token`, and async variants from `todoist_api_python.authentication` are not implemented as CLI commands.
- Custom SDK client injection is not exposed: the SDK accepts a custom `httpx.Client` and `request_id_fn`; the CLI only supports the default client/token path.
- Type-aware argument parsing is shallow: dates/datetimes are passed as strings unless the SDK accepts/normalizes them; JSON options exist for list/object parameters, but richer validation/help is still thin.
- Model-level docs are not surfaced: the SDK's model objects and constraints are serialized after the fact, but the CLI does not yet provide model schemas or enum/value discovery commands.
- Error output is minimal: SDK/httpx errors are printed as text; no structured error JSON mode yet.

### Completed-task tracking / external app changes

- Active-task endpoints (`get_tasks`, `filter_tasks`) only return active tasks. Once a task is completed in Todoist — especially from the native app — it disappears from the active context.
- The SDK does include completed-task endpoints: `get_completed_tasks_by_completion_date` and `get_completed_tasks_by_due_date`. These should be used to reconcile recent completions, not active-task queries alone.
- The current `heartbeat-context` command buckets active tasks only. It does not yet maintain a local sync ledger of “previously seen active task → later completed/missing/deleted”.
- Missing active tasks are ambiguous without reconciliation: they may be completed, deleted, moved, filtered out, or hidden by API limitations. The EA layer must not treat disappearance as failure or confusion without checking completed-task history.
- This needs a deliberate design before implementation: likely local state with last-seen task IDs, periodic completed-task backfill by completion date, and explicit distinction between completed, deleted/unknown, and still-active.
- The Todoist Sync API may be a better long-term foundation for robust reconciliation because it is designed for incremental sync, but this needs a focused evaluation against the Python SDK capabilities before building.
