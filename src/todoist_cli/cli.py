from __future__ import annotations

import argparse
import json
import sys
import threading
from collections.abc import Callable, Iterable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from .auth import load_token, missing_token_message
from .context import RESOURCE_TYPES, build_heartbeat_context, fetch_sync_payload
from .oauth import (
    OAuthTokenStore,
    build_authorization_url,
    build_token_exchange_request,
    build_token_refresh_request,
    post_token_request,
    redact_secret,
)
from .sdk import METHOD_SPECS, MethodSpec, iter_specs
from .sync_store import SyncStore, apply_completed_backfill, apply_sync_payload
from .webhooks import TodoistWebhookStore, run_webhook_server, verify_todoist_signature

BOOL_OPTIONS = {"is_favorite", "auto_reminder", "auto_parse_labels", "omit_personal", "collapsed"}
INT_OPTIONS = {"item_order", "priority", "duration", "minute_offset", "order", "day_order", "radius", "limit"}
FLOAT_OPTIONS = {"loc_lat", "loc_long"}
DATE_OPTIONS = {"due_date", "deadline_date", "since", "until"}
DATETIME_OPTIONS = {"due_datetime"}
JSON_OPTIONS = {"labels", "ids", "attachment", "uids_to_notify"}


def default_client_factory() -> Any:
    from todoist_api_python.api import TodoistAPI

    token = load_token()
    if not token:
        raise RuntimeError(missing_token_message())
    return TodoistAPI(token)


def serialize(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, list | tuple):
        return [serialize(v) for v in value]
    if isinstance(value, dict):
        return {str(k): serialize(v) for k, v in value.items()}
    if hasattr(value, "to_dict"):
        return serialize(value.to_dict())
    if hasattr(value, "dict"):
        return serialize(value.dict())
    if hasattr(value, "model_dump"):
        return serialize(value.model_dump())
    if hasattr(value, "__dict__"):
        return {k: serialize(v) for k, v in vars(value).items() if not k.startswith("_")}
    return str(value)


def flatten_paginated(value: Any, max_pages: int | None = None) -> list[Any]:
    out: list[Any] = []
    if not isinstance(value, Iterable) or isinstance(value, str | bytes | dict):
        return [value]
    for idx, page in enumerate(value):
        if max_pages is not None and idx >= max_pages:
            break
        if isinstance(page, list | tuple):
            out.extend(page)
        else:
            out.append(page)
    return out


def coerce_option(name: str, value: str | None) -> Any:
    if value is None:
        return None
    try:
        if name in BOOL_OPTIONS:
            return str(value).lower() in {"1", "true", "yes", "y", "on"}
        if name in INT_OPTIONS:
            return int(value)
        if name in FLOAT_OPTIONS:
            return float(value)
        if name in DATE_OPTIONS:
            return date.fromisoformat(value)
        if name in DATETIME_OPTIONS:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        if name in JSON_OPTIONS:
            return json.loads(value)
    except ValueError as exc:
        raise ValueError(f"Invalid value for {name}: {value!r}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON for {name}: {value!r}") from exc
    return value


def add_state_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--state-dir")
    parser.add_argument("--state-backend", choices=["json", "sqlite"], default=None)


def add_option(parser: argparse.ArgumentParser, name: str) -> None:
    flag = "--" + name.replace("_", "-")
    if name in BOOL_OPTIONS:
        parser.add_argument(flag, dest=name, nargs="?", const="true")
    else:
        parser.add_argument(flag, dest=name)


def add_spec_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser], spec: MethodSpec) -> None:
    parser = subparsers.add_parser(spec.action, help=spec.help or spec.name)
    parser.set_defaults(sdk_method=spec.name, spec=spec)
    for pos in spec.positional:
        parser.add_argument(pos)
    for opt in spec.options:
        add_option(parser, opt)
    parser.add_argument("--max-pages", type=int, default=None, help="Maximum SDK pages to consume for paginated calls.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="todoist-cli", description="Complete CLI wrapper for the Todoist Python SDK.")
    parser.add_argument("--format", choices=["json", "pretty"], default="json")
    sub = parser.add_subparsers(dest="group", required=True)

    groups: dict[str, list[MethodSpec]] = {}
    for spec in iter_specs():
        groups.setdefault(spec.group, []).append(spec)

    for group, specs in sorted(groups.items()):
        group_parser = sub.add_parser(group)
        group_sub = group_parser.add_subparsers(dest="action", required=True)
        for spec in specs:
            add_spec_parser(group_sub, spec)

    raw = sub.add_parser("raw", help="Call a TodoistAPI method by exact SDK name.")
    raw_sub = raw.add_subparsers(dest="raw_action", required=True)
    raw_call = raw_sub.add_parser("call")
    raw_call.add_argument("method", choices=sorted(METHOD_SPECS))
    raw_call.add_argument("args", nargs="*", help="Positional arguments")
    raw_call.add_argument("--kwargs", default="{}", help="JSON object of keyword arguments")
    raw_call.add_argument("--max-pages", type=int)
    raw_call.set_defaults(raw_call=True)
    for name in sorted(METHOD_SPECS):
        spec = METHOD_SPECS[name]
        p = raw_sub.add_parser(name, help=f"Raw SDK alias for {name}")
        p.set_defaults(sdk_method=name, spec=spec)
        for pos in spec.positional:
            p.add_argument(pos)
        for opt in spec.options:
            add_option(p, opt)
        p.add_argument("--max-pages", type=int)

    ctx = sub.add_parser("heartbeat-context", help="Read Todoist and emit compact heartbeat task context.")
    add_state_options(ctx)
    ctx.add_argument("--resources", default=",".join(RESOURCE_TYPES))
    ctx.add_argument("--now")
    ctx.add_argument("--no-sync", action="store_true", help="Build from existing local store without pulling first.")
    ctx.set_defaults(heartbeat_context=True)

    sync = sub.add_parser("sync", help="Maintain local Todoist sync state.")
    sync_sub = sync.add_subparsers(dest="sync_action", required=True)
    sync_pull = sync_sub.add_parser("pull", help="Pull Todoist /sync changes into the local store.")
    add_state_options(sync_pull)
    sync_pull.add_argument("--resources", default=",".join(RESOURCE_TYPES))
    sync_pull.add_argument("--full", action="store_true", help="Force a full sync with sync_token='*'.")
    sync_pull.set_defaults(sync_pull=True)
    sync_status = sync_sub.add_parser("status", help="Inspect local sync store status.")
    add_state_options(sync_status)
    sync_status.set_defaults(sync_status=True)
    sync_reset = sync_sub.add_parser("reset", help="Remove local sync state.")
    add_state_options(sync_reset)
    sync_reset.set_defaults(sync_reset=True)
    sync_migrate = sync_sub.add_parser("migrate", help="Migrate JSON sync state into SQLite.")
    add_state_options(sync_migrate)
    sync_migrate.add_argument("--remove-json", action="store_true")
    sync_migrate.set_defaults(sync_migrate=True)
    sync_backfill = sync_sub.add_parser("backfill-completed", help="Backfill recent completed tasks into the sync store.")
    add_state_options(sync_backfill)
    sync_backfill.add_argument("--window-days", type=int, default=14)
    sync_backfill.add_argument("--strategy", choices=["completion-date", "due-date"], default="completion-date")
    sync_backfill.add_argument("--now")
    sync_backfill.add_argument("--limit", type=int, default=200)
    sync_backfill.set_defaults(sync_backfill_completed=True)

    webhook = sub.add_parser("webhook", help="Handle Todoist webhook wake-up events.")
    webhook_sub = webhook.add_subparsers(dest="webhook_action", required=True)
    webhook_receive = webhook_sub.add_parser("receive", help="Verify and record one Todoist webhook payload, then pull sync.")
    add_state_options(webhook_receive)
    webhook_receive.add_argument("--secret", required=True)
    webhook_receive.add_argument("--signature", required=True)
    webhook_receive.add_argument("--body-file", required=True)
    webhook_receive.set_defaults(webhook_receive=True)
    webhook_serve = webhook_sub.add_parser("serve", help="Run a minimal Todoist webhook HTTP receiver.")
    add_state_options(webhook_serve)
    webhook_serve.add_argument("--secret", required=True)
    webhook_serve.add_argument("--host", default="127.0.0.1")
    webhook_serve.add_argument("--port", type=int, default=8080)
    webhook_serve.add_argument("--allow-event", action="append", default=[])
    webhook_serve.add_argument("--debounce-seconds", type=int, default=5)
    webhook_serve.add_argument("--once", action="store_true", help="Exit after accepting one non-debounced event.")
    webhook_serve.add_argument("--timeout", type=float, default=None, help="Seconds to wait in --once mode.")
    webhook_serve.set_defaults(webhook_serve=True)

    oauth = sub.add_parser("oauth", help="Todoist OAuth helper commands.")
    oauth_sub = oauth.add_subparsers(dest="oauth_action", required=True)
    oauth_url = oauth_sub.add_parser("authorize-url", help="Build a Todoist OAuth authorization URL.")
    oauth_url.add_argument("--client-id", required=True)
    oauth_url.add_argument("--redirect-uri", required=True)
    oauth_url.add_argument("--scope", required=True)
    oauth_url.add_argument("--state", required=True)
    oauth_url.set_defaults(oauth_authorize_url=True)
    oauth_exchange = oauth_sub.add_parser("exchange-token", help="Exchange an OAuth code and store returned tokens.")
    add_state_options(oauth_exchange)
    oauth_exchange.add_argument("--client-id", required=True)
    oauth_exchange.add_argument("--client-secret", required=True)
    oauth_exchange.add_argument("--code", required=True)
    oauth_exchange.add_argument("--redirect-uri", required=True)
    oauth_exchange.set_defaults(oauth_exchange_token=True)
    oauth_refresh = oauth_sub.add_parser("refresh-token", help="Refresh and store OAuth tokens.")
    add_state_options(oauth_refresh)
    oauth_refresh.add_argument("--client-id", required=True)
    oauth_refresh.add_argument("--client-secret", required=True)
    oauth_refresh.add_argument("--refresh-token")
    oauth_refresh.set_defaults(oauth_refresh_token=True)

    models = sub.add_parser("models", help="Inspect known CLI method specs.")
    models_sub = models.add_subparsers(dest="models_action", required=True)
    models_list = models_sub.add_parser("list")
    models_list.set_defaults(models_list=True)
    return parser


def namespace_to_kwargs(args: argparse.Namespace, spec: MethodSpec) -> tuple[list[Any], dict[str, Any]]:
    positional = [getattr(args, name) for name in spec.positional]
    kwargs: dict[str, Any] = {}
    for name in spec.options:
        raw = getattr(args, name, None)
        if raw is not None:
            kwargs[name] = coerce_option(name, raw)
    validate_friendly_args(spec, kwargs)
    return positional, kwargs


def validate_friendly_args(spec: MethodSpec, kwargs: dict[str, Any]) -> None:
    if spec.name in {"add_task", "update_task", "add_reminder", "update_reminder"}:
        supplied_due = [name for name in ("due_string", "due_date", "due_datetime") if kwargs.get(name) is not None]
        if len(supplied_due) > 1:
            raise ValueError(f"due options are mutually exclusive: {', '.join(supplied_due)}")
    if spec.name in {"add_location_reminder", "update_location_reminder"}:
        location_fields = {"loc_lat", "loc_long", "loc_trigger"}
        supplied = {name for name in location_fields if kwargs.get(name) is not None}
        if supplied and supplied != location_fields:
            raise ValueError("location reminders require loc_lat, loc_long, and loc_trigger together")


def print_result(value: Any, fmt: str) -> None:
    data = serialize(value)
    if fmt == "pretty":
        print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(json.dumps(data, ensure_ascii=False, separators=(",", ":")))


def print_error(exc: Exception, fmt: str) -> None:
    error = {
        "status": "error",
        "error_type": type(exc).__name__,
        "message": str(exc),
    }
    status_code = getattr(exc, "status_code", None)
    if status_code is None and getattr(exc, "response", None) is not None:
        status_code = getattr(exc.response, "status_code", None)
    request_id = getattr(exc, "request_id", None)
    if request_id is None and getattr(exc, "response", None) is not None:
        request_id = getattr(exc.response, "headers", {}).get("x-request-id")
    if request_id:
        error["request_id"] = request_id
    if status_code is not None:
        error["status_code"] = status_code
        error["retryable"] = int(status_code) in {408, 409, 425, 429, 500, 502, 503, 504}
    print(str(exc), file=sys.stderr)
    if fmt == "pretty":
        print(json.dumps(error, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(json.dumps(error, ensure_ascii=False, separators=(",", ":")))


def sync_state_to_payload(state: dict[str, Any]) -> dict[str, Any]:
    resources = state.get("resources", {})
    payload = {key: list(resources.get(key, {}).values()) for key in RESOURCE_TYPES}
    payload["completed_items"] = state.get("completed_items", {})
    payload["deleted_items"] = state.get("deleted_items", {})
    return payload


def sync_status_payload(store: SyncStore) -> dict[str, Any]:
    state = store.load_state()
    resources = state.get("resources", {})
    return {
        "configured": True,
        "state_backend": store.backend,
        "state_file": str(store.db_file if store.backend == "sqlite" else store.state_file),
        "legacy_json_state_file": str(store.state_file),
        "corrupt_state_recovered": store.corrupt_state_recovered,
        "sync_token_present": bool(state.get("sync_token")),
        "last_sync_at": state.get("last_sync_at"),
        "last_full_sync_at": state.get("last_full_sync_at"),
        "counts": {key: len(resources.get(key, {})) for key in sorted(resources)},
        "completed_items": len(state.get("completed_items", {})),
        "deleted_items": len(state.get("deleted_items", {})),
        "change_log_entries": len(state.get("change_log", [])),
    }


def store_from_args(args: argparse.Namespace) -> SyncStore:
    backend = getattr(args, "state_backend", None)
    return SyncStore(
        Path(args.state_dir).expanduser() if getattr(args, "state_dir", None) else None,
        backend=backend if backend else None,
    )


def sqlite_store_for_migration(args: argparse.Namespace) -> SyncStore:
    return SyncStore(
        Path(args.state_dir).expanduser() if getattr(args, "state_dir", None) else None,
        backend="sqlite",
    )


def flatten_completed_pages(value: Any) -> list[dict[str, Any]]:
    return [item for item in flatten_paginated(value) if isinstance(item, dict)]


def backfill_window(now_iso: str | None, window_days: int) -> tuple[date, date]:
    now = datetime.fromisoformat(now_iso.replace("Z", "+00:00")) if now_iso else datetime.now()
    until = now.date()
    since = until - timedelta(days=window_days)
    return since, until


def is_invalid_sync_token_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code is None and getattr(exc, "response", None) is not None:
        status_code = getattr(exc.response, "status_code", None)
    text = str(exc).lower()
    return status_code in {400, 401} and "sync" in text and "token" in text


def pull_sync_into_store(
    store: SyncStore,
    resources: list[str],
    full: bool,
    fetcher: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    state = store.load_state()
    sync_token = "*" if full or store.corrupt_state_recovered or not state.get("sync_token") else state["sync_token"]
    try:
        payload = fetcher(sync_token=sync_token, resource_types=resources)
    except Exception as exc:
        if sync_token != "*" and is_invalid_sync_token_error(exc):
            payload = fetcher(sync_token="*", resource_types=resources)
        else:
            raise
    return apply_sync_payload(store, payload)


def sync_once(store: SyncStore, fetcher: Callable[..., dict[str, Any]]) -> dict[str, Any]:
    state = store.load_state()
    sync_token = "*" if store.corrupt_state_recovered or not state.get("sync_token") else state["sync_token"]
    return apply_sync_payload(store, fetcher(sync_token=sync_token, resource_types=RESOURCE_TYPES))


def models_payload() -> dict[str, Any]:
    return {
        "methods": {
            name: {
                "group": spec.group,
                "action": spec.action,
                "positional": list(spec.positional),
                "options": list(spec.options),
                "mutating": spec.mutating,
                "paginated": spec.paginated,
            }
            for name, spec in sorted(METHOD_SPECS.items())
        }
    }


def invoke(client: Any, method: str, positional: list[Any], kwargs: dict[str, Any], max_pages: int | None) -> Any:
    fn = getattr(client, method)
    result = fn(*positional, **kwargs)
    spec = METHOD_SPECS.get(method)
    if spec and spec.paginated:
        return flatten_paginated(result, max_pages=max_pages)
    return result


def main(
    argv: list[str] | None = None,
    client_factory: Callable[[], Any] | None = None,
    sync_fetcher: Callable[..., dict[str, Any]] | None = None,
    oauth_post: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    fmt = getattr(args, "format", "json")
    try:
        if getattr(args, "sync_status", False):
            print_result(sync_status_payload(store_from_args(args)), fmt)
            return 0
        if getattr(args, "sync_reset", False):
            store = store_from_args(args)
            store.reset()
            print_result({"status": "reset", "state_backend": store.backend, "state_file": str(store.db_file if store.backend == "sqlite" else store.state_file)}, fmt)
            return 0
        if getattr(args, "sync_migrate", False):
            store = sqlite_store_for_migration(args)
            state = store.migrate_json_to_sqlite(remove_json=args.remove_json)
            payload = sync_status_payload(store)
            payload["status"] = "migrated"
            payload["migrated_counts"] = {key: len(state.get("resources", {}).get(key, {})) for key in sorted(state.get("resources", {}))}
            print_result(payload, fmt)
            return 0
        if getattr(args, "sync_pull", False):
            store = store_from_args(args)
            resources = [part.strip() for part in args.resources.split(",") if part.strip()]
            fetcher = sync_fetcher or fetch_sync_payload
            pull_sync_into_store(store, resources, args.full, fetcher)
            print_result(sync_status_payload(store), fmt)
            return 0
        if getattr(args, "sync_backfill_completed", False):
            store = store_from_args(args)
            since, until = backfill_window(args.now, args.window_days)
            client = (client_factory or default_client_factory)()
            if args.strategy == "due-date":
                result = client.get_completed_tasks_by_due_date(since=since, until=until, limit=args.limit)
            else:
                result = client.get_completed_tasks_by_completion_date(since=since, until=until, limit=args.limit)
            state = apply_completed_backfill(store, flatten_completed_pages(result), args.window_days, args.strategy)
            payload = sync_status_payload(store)
            payload["completed_backfill"] = {
                "window_days": state["completed_backfill"].get("window_days"),
                "last_run_at": state["completed_backfill"].get("last_run_at"),
            }
            print_result(payload, fmt)
            return 0
        if getattr(args, "heartbeat_context", False):
            store = store_from_args(args)
            state = store.load_state()
            if not args.no_sync:
                resources = [part.strip() for part in args.resources.split(",") if part.strip()]
                fetcher = sync_fetcher or fetch_sync_payload
                state = pull_sync_into_store(store, resources, False, fetcher)
            payload = sync_state_to_payload(state)
            context = build_heartbeat_context(payload, now_iso=args.now)
            context["source"] = "todoist_sync_store"
            context["counts"]["completed"] = len(state.get("completed_items", {}))
            context["counts"]["deleted_unknown"] = len(state.get("deleted_items", {}))
            print_result(context, fmt)
            return 0
        if getattr(args, "webhook_receive", False):
            store = store_from_args(args)
            body = Path(args.body_file).read_bytes()
            if not verify_todoist_signature(body, args.signature, args.secret):
                raise PermissionError("Invalid Todoist webhook signature")
            payload = json.loads(body.decode("utf-8"))
            receipt = TodoistWebhookStore(store.state_dir).record_receipt(payload)
            sync_once(store, sync_fetcher or fetch_sync_payload)
            print_result({"status": "accepted", "receipt": receipt, "sync": sync_status_payload(store)}, fmt)
            return 0
        if getattr(args, "webhook_serve", False):
            store = store_from_args(args)
            served = threading.Event()

            def run_sync() -> None:
                sync_once(store, sync_fetcher or fetch_sync_payload)
                served.set()

            server = run_webhook_server(
                host=args.host,
                port=args.port,
                state_dir=store.state_dir,
                secret=args.secret,
                allowed_events=set(args.allow_event or []),
                debounce_seconds=args.debounce_seconds,
                sync_callback=run_sync,
            )
            if args.once:
                if not served.wait(args.timeout):
                    server.shutdown()
                    raise TimeoutError("No accepted Todoist webhook received before timeout")
                server.shutdown()
                print_result({"status": "served_once", "address": f"{args.host}:{args.port}"}, fmt)
                return 0
            print_result({"status": "serving", "address": f"{args.host}:{args.port}", "path": "/todoist/webhook"}, fmt)
            try:
                threading.Event().wait()
            except KeyboardInterrupt:
                server.shutdown()
            return 0
        if getattr(args, "oauth_authorize_url", False):
            print_result(
                {
                    "authorize_url": build_authorization_url(args.client_id, args.redirect_uri, args.scope, args.state),
                    "client_id": redact_secret(args.client_id),
                    "redirect_uri": args.redirect_uri,
                    "scope": args.scope,
                },
                fmt,
            )
            return 0
        if getattr(args, "oauth_exchange_token", False):
            store = OAuthTokenStore(store_from_args(args).state_dir)
            request_payload = build_token_exchange_request(args.client_id, args.client_secret, args.code, args.redirect_uri)
            tokens = (oauth_post or post_token_request)(request_payload["url"], request_payload["body"])
            store.save_tokens(tokens)
            print_result({"status": "stored", "tokens": store.redacted_summary()}, fmt)
            return 0
        if getattr(args, "oauth_refresh_token", False):
            store = OAuthTokenStore(store_from_args(args).state_dir)
            refresh_token = args.refresh_token or store.load_tokens().get("refresh_token")
            if not refresh_token:
                raise ValueError("Missing refresh token; pass --refresh-token or exchange/store tokens first")
            request_payload = build_token_refresh_request(args.client_id, args.client_secret, refresh_token)
            tokens = (oauth_post or post_token_request)(request_payload["url"], request_payload["body"])
            store.save_tokens(tokens)
            print_result({"status": "stored", "tokens": store.redacted_summary()}, fmt)
            return 0
        if getattr(args, "models_list", False):
            print_result(models_payload(), fmt)
            return 0
        if getattr(args, "raw_call", False):
            method = args.method
            client = (client_factory or default_client_factory)()
            kwargs = json.loads(args.kwargs)
            print_result(invoke(client, method, list(args.args), kwargs, args.max_pages), fmt)
            return 0
        method = args.sdk_method
        spec = METHOD_SPECS[method]
        positional, kwargs = namespace_to_kwargs(args, spec)
        client = (client_factory or default_client_factory)()
        print_result(invoke(client, method, positional, kwargs, args.max_pages), fmt)
        return 0
    except Exception as exc:
        print_error(exc, fmt)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
