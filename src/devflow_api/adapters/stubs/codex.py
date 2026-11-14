"""Offline Codex adapter."""

from devflow_api.adapters.capability import ExecutionMode, IntegrationCapability
from devflow_api.adapters.protocols.codex import CodexCLIRequest, CodexCLIResult
from devflow_api.adapters.stubs._base import OfflineAdapter


class CodexStubAdapter(OfflineAdapter):
    _capability = IntegrationCapability(
        name="codex",
        execution_mode=ExecutionMode.CLI_HANDOFF,
        supported_actions=["request_code_generation", "execute_approved_request"],
        auth_required=False,
        auth_type="cli_auth",
        available_in_phase_0=False,
        notes=(
            "CLI authentication and plan limits may apply. "
            "Free or unlimited access is not guaranteed. Phase 0 performs no CLI execution."
        ),
    )

    def request_code_generation(
        self, description: str, language: str, workspace_path: str
    ) -> CodexCLIRequest:
        return CodexCLIRequest(description, language, workspace_path)

    async def execute_approved_request(self, request: CodexCLIRequest) -> CodexCLIResult:
        if not request.approved:
            raise ValueError("CodexCLIRequest must be explicitly approved before execution.")
        return CodexCLIResult(
            stdout="[Phase 0 stub] No real Codex execution.",
            stderr="",
            exit_code=0,
            timed_out=False,
        )
