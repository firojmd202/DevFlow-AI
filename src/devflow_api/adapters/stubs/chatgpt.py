"""Offline ChatGPT adapter."""

from devflow_api.adapters.capability import ExecutionMode, IntegrationCapability
from devflow_api.adapters.protocols.chatgpt import ChatGPTResponse
from devflow_api.adapters.stubs._base import OfflineAdapter


class ChatGPTStubAdapter(OfflineAdapter):
    _capability = IntegrationCapability(
        name="chatgpt",
        execution_mode=ExecutionMode.AUTOMATED_API,
        supported_actions=["complete"],
        auth_required=True,
        auth_type="api_key",
        available_in_phase_0=False,
    )

    async def complete(self, prompt: str, model: str) -> ChatGPTResponse:
        return ChatGPTResponse()
