"""Canonical JSON used to bind MCP arguments to approvals and audit events."""

import json
from hashlib import sha256


def _validate_json(value: object) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("MCP argument keys must be strings")
            _validate_json(item)
    elif isinstance(value, list):
        for item in value:
            _validate_json(item)
    elif value is not None and type(value) not in (bool, int, float, str):
        raise ValueError("MCP arguments must contain only JSON values")


def canonical_arguments(arguments: dict[str, object]) -> str:
    _validate_json(arguments)
    return json.dumps(arguments, sort_keys=True, separators=(",", ":"), allow_nan=False)


def hash_arguments(arguments: dict[str, object]) -> str:
    return sha256(canonical_arguments(arguments).encode("utf-8")).hexdigest()
