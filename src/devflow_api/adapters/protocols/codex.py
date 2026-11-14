"""Codex integration contract."""

from dataclasses import dataclass
from typing import Protocol

from devflow_api.adapters.protocols.base import BaseAdapterProtocol


@dataclass
class CodexCLIRequest:
    description: str
    language: str
    workspace_path: str
    approved: bool = False
    timeout_seconds: int = 30


@dataclass
class CodexCLIResult:
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool
    stub: bool = True


class CodexAdapterProtocol(BaseAdapterProtocol, Protocol):
    def request_code_generation(
        self, description: str, language: str, workspace_path: str
    ) -> CodexCLIRequest: ...

    async def execute_approved_request(self, request: CodexCLIRequest) -> CodexCLIResult:
        """Require explicit approval. Future live execution is limited to authorized workspaces."""
        ...
