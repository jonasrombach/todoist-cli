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

Beyond the SDK wrapper, the repo includes a local automation layer useful for humans, shell scripts, dashboards, and AI agents:

- Structured JSON errors, including `status_code`, `request_id`, and `retryable` where the SDK/API exposes them.
- Typed option coercion for dates, datetimes, numbers, booleans, and JSON options, plus validation for common dangerous/friendly-command combinations.
- SQLite-backed incremental `/sync` state under `${XDG_STATE_HOME:-~/.local/state}/todoist-cli/sync-state.sqlite3`, with JSON fallback/selection, migration from legacy `sync-state.json`, and full-sync recovery for rejected tokens and corrupt local state.
- `heartbeat-context` built from the local sync store with semantic buckets for overdue, today, next-7-days, postponed, high-priority unscheduled, completed, and deleted evidence.
- Completed-task backfill by completion date and due date.
- Todoist webhook HMAC verification, privacy-preserving receipt logging, and a minimal HTTP receiver via `todoist-cli webhook serve`.
- OAuth helper flow: authorization URL, token exchange, token refresh, secure local token storage with `0600`, and redacted output.
- `todoist-cli models list` for method/spec discovery.
- `/sync` batch payload helper primitives in the Python package for dependent writes.

## Operational notes

No high-priority functional roadmap items remain for a local Todoist CLI and sync workflow.

Things intentionally not built until there is a concrete need:

- Production webhook hosting/relay choice. Todoist requires a public HTTPS callback without an explicit port; this depends on deployment infrastructure, not the CLI package itself.
- Broad non-SDK Todoist API v1 expansion such as uploads, templates, activity, backups, email helpers, workspace/admin operations, or MCP integration.
- Async CLI mode and custom SDK client injection, unless this grows into a long-running daemon or needs advanced timeout/proxy/tracing behavior.

## Open topics for universal reuse

The repo is public and no longer requires agent-specific private code to run as a CLI. It should work for a normal shell user or an agent runner such as OpenClaw, Claude Code, Codex, or Cursor as long as they provide Todoist credentials. The remaining work is about packaging, documentation, and integration polish rather than hidden local internals.

- **Remove or generalize the Hermes dotenv fallback.** The CLI currently falls back to `~/.hermes/.env` when `TODOIST_CLI_ENV_FILE` is not set. That is convenient for Jonas' local automation but smells private in a public tool. Prefer either documenting it as legacy-only, moving to a neutral `~/.config/todoist-cli/env`, or removing it before a broader release. Keep env-var config as the primary path, consistent with Twelve-Factor config separation.
- **Publish/install path.** The README only documents `pip install -e .`. For universal use, add standard installation guidance: PyPI package if published, `pipx install git+https://...`, or `uv tool install git+https://...`. Also document Python version and the fact that SQLite comes from Python's stdlib but may be absent in unusual Python builds.
- **Agent contract.** Add an explicit machine-consumption contract for OpenClaw/Claude/Codex/etc.: stdout is JSON only, diagnostics go to stderr, non-zero exit means failure, structured errors use `{status,error_type,message,...}`, global flags such as `--format` must precede the subcommand, and mutating commands do not ask for confirmation.
- **Command reference.** Add generated or maintained help docs for all command groups, including `sync`, `webhook`, `oauth`, `models`, `raw`, and SDK resource groups. Right now examples are useful but not enough for a new user or a non-Hermes agent to discover the full surface without running `--help` repeatedly.
- **State and privacy docs.** Document exactly what is stored in `sync-state.sqlite3`, `oauth-tokens.json`, and `webhook-receipts.jsonl`; how to choose `--state-dir`; how to force `--state-backend json`; how to migrate old JSON state with `sync migrate`; and how to reset/remove local data safely.
- **OAuth/webhook app setup guide.** Todoist webhooks require an app OAuth flow; they do not fire by default for the app creator. Add a step-by-step guide for creating a Todoist app, selecting scopes, setting redirect/callback URLs, exchanging/refreshing tokens, and deploying a public HTTPS webhook endpoint.
- **API v1 coverage strategy.** The installed synchronous Python SDK is covered, but Todoist API v1 contains capabilities outside the SDK-wrapper surface: uploads, templates, backups, activity log, workspace/admin features, dynamic client registration, MCP, and some `/sync` write operations. Decide whether this project stays “SDK wrapper + sync automation” or grows first-class non-SDK commands.
- **Plan/permission-aware behavior.** Todoist API features vary by user/workspace plan. Add clearer handling and docs for restricted features such as reminders, comments, backups, uploads, filters, templates, and activity logs.
- **Cross-platform support.** XDG state paths are Unix-friendly. Add Windows/macOS notes or use a platform directory helper if broad desktop use matters.
- **Shell completion and examples.** Add completion generation and more copy-pasteable recipes for humans and agents: dry read flows, safe task creation, sync bootstrap, heartbeat context, webhook local test, OAuth test flow, and JSON parsing with `jq`.
