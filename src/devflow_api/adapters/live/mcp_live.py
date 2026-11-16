"""Live MCP adapter. Invocation requires trusted context through MCPService."""

from devflow_api.adapters.capability import ExecutionMode, IntegrationCapability
from devflow_api.adapters.exceptions import MCPPermissionError
from devflow_api.adapters.protocols.mcp import MCPResponse
from devflow_core.config import Settings
from devflow_core.mcp_config import MCPServerConfig


class MCPLiveAdapter:
    name = "mcp"

    def __init__(self, settings: Settings) -> None:
        self._configured = any(server.enabled for server in MCPServerConfig.from_settings(settings))

    @property
    def capability(self) -> IntegrationCapability:
        return IntegrationCapability(
            name=self.name,
            execution_mode=ExecutionMode.AUTOMATED_API,
            supported_actions=["call_tool"],
            auth_required=False,
            auth_type=None,
            available_in_phase_0=False,
        )

    async def health_check(self) -> dict[str, str]:
        return {
            "status": "configured" if self._configured else "unavailable",
            "integration": self.name,
            "execution_mode": ExecutionMode.AUTOMATED_API,
        }

    async def call_tool(self, server: str, tool: str, args: dict[str, object]) -> MCPResponse:
        # The Phase 0 protocol supplies no trusted actor or workflow context.
        raise MCPPermissionError(server, tool)
