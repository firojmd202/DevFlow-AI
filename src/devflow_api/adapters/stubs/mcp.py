"""Offline MCP adapter."""

from devflow_api.adapters.capability import ExecutionMode, IntegrationCapability
from devflow_api.adapters.protocols.mcp import MCPResponse
from devflow_api.adapters.stubs._base import OfflineAdapter


class MCPStubAdapter(OfflineAdapter):
    _capability = IntegrationCapability(
        name="mcp",
        execution_mode=ExecutionMode.AUTOMATED_API,
        supported_actions=["call_tool"],
        auth_required=False,
        auth_type=None,
        available_in_phase_0=False,
    )

    async def call_tool(self, server: str, tool: str, args: dict[str, object]) -> MCPResponse:
        return MCPResponse()
