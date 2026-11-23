"""Redact configured credentials and keep model input inside data sections."""

import re

from pydantic import SecretStr

from devflow_core.config import Settings
from devflow_core.logging import RedactSecretsProcessor

_SECRET_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b")
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def redact_text(value: str, settings: Settings) -> str:
    secrets = tuple(
        item.get_secret_value()
        for field in type(settings).model_fields
        if isinstance(item := getattr(settings, field), SecretStr)
    )
    safe = RedactSecretsProcessor(secrets)(None, "info", {"value": value})["value"]
    return _SECRET_PATTERN.sub("[REDACTED]", str(safe))


def prompt_data(value: str, settings: Settings) -> str:
    clean = _CONTROL.sub("", value.replace("\r\n", "\n").replace("\r", "\n"))
    # Escape delimiters even if the model input contains exact protocol markers.
    return redact_text(clean, settings).replace("---", "— — —").replace("===", "＝ ＝ ＝")
