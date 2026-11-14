"""Offline Figma adapter."""

from devflow_api.adapters.capability import ExecutionMode, IntegrationCapability
from devflow_api.adapters.protocols.figma import FigmaResponse
from devflow_api.adapters.stubs._base import OfflineAdapter


class FigmaStubAdapter(OfflineAdapter):
    _capability = IntegrationCapability(
        name="figma",
        execution_mode=ExecutionMode.AUTOMATED_API,
        supported_actions=["get_file"],
        auth_required=True,
        auth_type="token",
        available_in_phase_0=False,
    )

    async def get_file(self, file_key: str) -> FigmaResponse:
        return FigmaResponse()
