from __future__ import annotations

import os
from pathlib import Path

TOKEN_ENV_VARS = ("TODOIST_API_TOKEN", "TODOIST_TOKEN")
DEFAULT_ENV_FILES = (Path.home() / ".config" / "todoist-cli" / "env",)


def load_dotenv_token(env_file: Path) -> str | None:
    if not env_file.exists():
        return None
    for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() in TOKEN_ENV_VARS:
            return value.strip().strip('"').strip("'") or None
    return None


def candidate_env_files() -> tuple[Path, ...]:
    configured = os.environ.get("TODOIST_CLI_ENV_FILE")
    if configured:
        return (Path(configured).expanduser(),)
    return DEFAULT_ENV_FILES


def load_token() -> str | None:
    for env_var in TOKEN_ENV_VARS:
        token = os.environ.get(env_var)
        if token:
            return token.strip()
    for env_file in candidate_env_files():
        token = load_dotenv_token(env_file)
        if token:
            return token
    return None


def missing_token_message() -> str:
    env_hint = ", ".join(str(path) for path in candidate_env_files())
    return (
        "Missing TODOIST_API_TOKEN in environment or configured env file "
        f"({env_hint}). Set TODOIST_CLI_ENV_FILE to use a custom dotenv path."
    )
