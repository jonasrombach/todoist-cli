from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class BatchCommand:
    type: str
    args: dict[str, Any]
    uuid: str | None = None
    temp_id: str | None = None


def build_batch_payload(commands: list[BatchCommand]) -> dict[str, Any]:
    return {"commands": [_command_to_payload(command) for command in commands]}


def map_temp_ids(commands: list[BatchCommand], temp_id_mapping: dict[str, str]) -> list[BatchCommand]:
    return [replace(command, args=_map_value(command.args, temp_id_mapping)) for command in commands]


def _command_to_payload(command: BatchCommand) -> dict[str, Any]:
    payload = {
        "type": command.type,
        "uuid": command.uuid or str(uuid4()),
        "args": command.args,
    }
    if command.temp_id:
        payload["temp_id"] = command.temp_id
    return payload


def _map_value(value: Any, temp_id_mapping: dict[str, str]) -> Any:
    if isinstance(value, str) and value.startswith("$"):
        return temp_id_mapping.get(value[1:], value)
    if isinstance(value, dict):
        return {k: _map_value(v, temp_id_mapping) for k, v in value.items()}
    if isinstance(value, list):
        return [_map_value(v, temp_id_mapping) for v in value]
    return value
