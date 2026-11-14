"""Offline Claude adapter."""

from devflow_api.adapters.capability import ExecutionMode, IntegrationCapability
from devflow_api.adapters.protocols.claude import ClaudeResponse
from devflow_api.adapters.stubs._base import OfflineAdapter


class ClaudeStubAdapter(OfflineAdapter):
    _capability = IntegrationCapability(
        name="claude",
        execution_mode=ExecutionMode.AUTOMATED_API,
        supported_actions=["complete"],
        auth_required=True,
        auth_type="api_key",
        available_in_phase_0=False,
    )

    async def complete(self, prompt: str, model: str) -> ClaudeResponse:
        return ClaudeResponse()
