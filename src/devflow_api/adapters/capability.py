"""Execution modes and capability metadata."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel


class ExecutionMode(StrEnum):
    AUTOMATED_API = "automated_api"
    CLI_HANDOFF = "cli_handoff"
    MANUAL_HANDOFF = "manual_handoff"
    UNKNOWN = "unknown"


class IntegrationCapability(BaseModel):
    name: str
    execution_mode: ExecutionMode
    supported_actions: list[str]
    auth_required: bool
    auth_type: str | None
    available_in_phase_0: Literal[False]
    notes: str = ""
