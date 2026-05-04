from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from .context import build_heartbeat_context, fetch_sync_payload
from .sdk import METHOD_SPECS, MethodSpec, iter_specs

BOOL_OPTIONS = {"is_favorite", "auto_reminder", "omit_personal", "collapsed"}
INT_OPTIONS = {"item_order", "priority", "duration", "minute_offset", "order", "radius", "limit"}
FLOAT_OPTIONS = {"loc_lat", "loc_long"}
JSON_OPTIONS = {"labels", "ids", "attachment", "uids_to_notify"}
MUTATION_ENV = "TODOIST_CLI_ASSUME_YES"


def load_token() -> str | None:
    token = os.environ.get("TODOIST_API_TOKEN") or os.environ.get("TODOIST_TOKEN")
    if token:
        return token.strip()
    env_file = Path.home() / ".hermes" / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() in {"TODOIST_API_TOKEN", "TODOIST_TOKEN"}:
                return value.strip().strip('"').strip("'") or None
    return None


def default_client_factory() -> Any:
    from todoist_api_python.api import TodoistAPI

    token = load_token()
    if not token:
        raise RuntimeError("Missing TODOIST_API_TOKEN in environment or ~/.hermes/.env")
    return TodoistAPI(token)


def serialize(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
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
    if name in BOOL_OPTIONS:
        return str(value).lower() in {"1", "true", "yes", "y", "on"}
    if name in INT_OPTIONS:
        return int(value)
    if name in FLOAT_OPTIONS:
        return float(value)
    if name in JSON_OPTIONS:
        return json.loads(value)
    return value


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
    if spec.mutating:
        parser.add_argument("--yes", action="store_true", help="Confirm this mutating Todoist operation.")


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
    raw_call.add_argument("--yes", action="store_true")
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
        if spec.mutating:
            p.add_argument("--yes", action="store_true")

    ctx = sub.add_parser("heartbeat-context", help="Read Todoist and emit compact heartbeat task context.")
    ctx.set_defaults(heartbeat_context=True)
    return parser


def namespace_to_kwargs(args: argparse.Namespace, spec: MethodSpec) -> tuple[list[Any], dict[str, Any]]:
    positional = [getattr(args, name) for name in spec.positional]
    kwargs: dict[str, Any] = {}
    for name in spec.options:
        raw = getattr(args, name, None)
        if raw is not None:
            kwargs[name] = coerce_option(name, raw)
    return positional, kwargs


def is_confirmed(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "yes", False)) or os.environ.get(MUTATION_ENV) in {"1", "true", "yes"}


def print_result(value: Any, fmt: str) -> None:
    data = serialize(value)
    if fmt == "pretty":
        print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(json.dumps(data, ensure_ascii=False, separators=(",", ":")))


def invoke(client: Any, method: str, positional: list[Any], kwargs: dict[str, Any], max_pages: int | None) -> Any:
    fn = getattr(client, method)
    result = fn(*positional, **kwargs)
    spec = METHOD_SPECS.get(method)
    if spec and spec.paginated:
        return flatten_paginated(result, max_pages=max_pages)
    return result


def main(argv: list[str] | None = None, client_factory: Callable[[], Any] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    fmt = getattr(args, "format", "json")
    try:
        if getattr(args, "heartbeat_context", False):
            print_result(build_heartbeat_context(fetch_sync_payload()), fmt)
            return 0
        if getattr(args, "raw_call", False):
            method = args.method
            spec = METHOD_SPECS[method]
            if spec.mutating and not is_confirmed(args):
                print(f"{method} requires --yes", file=sys.stderr)
                return 2
            client = (client_factory or default_client_factory)()
            kwargs = json.loads(args.kwargs)
            print_result(invoke(client, method, list(args.args), kwargs, args.max_pages), fmt)
            return 0
        method = args.sdk_method
        spec = METHOD_SPECS[method]
        if spec.mutating and not is_confirmed(args):
            print(f"{method} requires --yes", file=sys.stderr)
            return 2
        positional, kwargs = namespace_to_kwargs(args, spec)
        client = (client_factory or default_client_factory)()
        print_result(invoke(client, method, positional, kwargs, args.max_pages), fmt)
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
