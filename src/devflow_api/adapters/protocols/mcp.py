"""MCP integration contract."""

from typing import Protocol

from pydantic import BaseModel

from devflow_api.adapters.protocols.base import BaseAdapterProtocol


class MCPResponse(BaseModel):
    stub: bool = True


class MCPAdapterProtocol(BaseAdapterProtocol, Protocol):
    async def call_tool(self, server: str, tool: str, args: dict[str, object]) -> MCPResponse: ...
