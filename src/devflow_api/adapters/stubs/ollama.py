"""Offline Ollama adapter."""

from devflow_api.adapters.capability import ExecutionMode, IntegrationCapability
from devflow_api.adapters.protocols.ollama import OllamaResponse
from devflow_api.adapters.stubs._base import OfflineAdapter


class OllamaStubAdapter(OfflineAdapter):
    _capability = IntegrationCapability(
        name="ollama",
        execution_mode=ExecutionMode.AUTOMATED_API,
        supported_actions=["generate"],
        auth_required=False,
        auth_type=None,
        available_in_phase_0=False,
    )

    async def generate(self, model: str, prompt: str) -> OllamaResponse:
        return OllamaResponse()
