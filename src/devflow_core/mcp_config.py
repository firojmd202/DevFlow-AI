"""Validated operator configuration for local MCP servers."""

from __future__ import annotations

from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter

type ToolClassification = Literal["read_only", "consequential", "unknown"]
type Nonempty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class MCPServerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    name: Nonempty
    command: list[Nonempty] = Field(min_length=1)
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict, repr=False)
    timeout_seconds: int = Field(default=30, gt=0)
    enabled: bool = True
    allowed_tools: list[Nonempty] = Field(default_factory=lambda: ["*"])
    tool_classifications: dict[str, ToolClassification] = Field(default_factory=dict)
    tool_schemas: dict[str, dict[str, object]] = Field(default_factory=dict, repr=False)

    @classmethod
    def from_settings(cls, settings: MCPSettings) -> list[MCPServerConfig]:
        return parse_mcp_config(settings.MCP_SERVERS_CONFIG)


class MCPSettings(Protocol):
    """Settings interface used by the MCP configuration model."""

    MCP_SERVERS_CONFIG: str


_CONFIGS = TypeAdapter(list[MCPServerConfig])


def parse_mcp_config(raw: str) -> list[MCPServerConfig]:
    if not raw.strip():
        return []
    configs = _CONFIGS.validate_json(raw)
    if len({config.name for config in configs}) != len(configs):
        raise ValueError("MCP server names must be unique")
    return configs
