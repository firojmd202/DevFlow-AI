"""Offline acceptance tests for Wave 2 MCP context retrieval."""

import ast
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr

from devflow_api.adapters import mcp_adapter
from devflow_api.adapters.exceptions import (
    MCPContextFailureError,
    MCPPermissionError,
    MCPServerNotFoundError,
    MCPToolSchemaError,
)
from devflow_api.adapters.mcp_adapter import MCPClientAdapter
from devflow_api.adapters.mcp_client import MCPClient, MCPServerConfig
from devflow_api.repositories.approval import AuditLogRepository
from devflow_core.config import Settings
from devflow_core.mcp_arguments import hash_arguments
from tests.mcp_fakes import FakeServer

ARGS: dict[str, object] = {"query": "private input"}


@pytest.fixture
def config() -> MCPServerConfig:
    return MCPServerConfig(
        name="local",
        command=["server"],
        allowed_tools=["read", "write", "unclassified"],
        tool_classifications={"read": "read_only", "write": "consequential"},
        tool_schemas={
            "read": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            }
        },
        env={"EXPLICIT": "${GITHUB_TOKEN}"},
        timeout_seconds=1,
    )


@pytest.fixture
def audit() -> AsyncMock:
    return AsyncMock(spec=AuditLogRepository)


@pytest.fixture
async def transport(monkeypatch: pytest.MonkeyPatch) -> tuple[FakeServer, AsyncMock]:
    process = FakeServer()
    spawn = AsyncMock(return_value=process)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    return process, spawn


def make_adapter(config: MCPServerConfig, audit: AsyncMock, **changes: object) -> MCPClientAdapter:
    settings = Settings.model_validate({"GITHUB_TOKEN": SecretStr("private-token"), **changes})
    return MCPClientAdapter(MCPClient([config], settings), audit, settings)


def test_adapter_has_no_sdk_imports() -> None:
    source = Path(mcp_adapter.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    imports.update(
        name.name for node in ast.walk(tree) if isinstance(node, ast.Import) for name in node.names
    )
    assert not any(name and name.split(".")[0] in {"mcp", "mcp_types"} for name in imports)


async def test_context_discovery_and_invocation(
    config: MCPServerConfig, audit: AsyncMock, transport: tuple[FakeServer, AsyncMock]
) -> None:
    process, _ = transport
    process.outcome = "paginated"
    adapter = make_adapter(config, audit)
    assert await adapter.list_tools("local") == ("read",)
    assert process.calls.count("tools/list") == 2
    assert "tools/call" not in process.calls
    process.outcome = "success"
    result = await adapter.retrieve_context("local", "read", ARGS, required=False)
    assert result.model_dump() == {
        "content": "result",
        "server": "local",
        "tool": "read",
        "required": False,
        "truncated": False,
    }
    assert process.arguments == ARGS
    audit.log_event.assert_awaited_once_with(
        "mcp_tool_invoked",
        "system",
        payload={
            "server_name": "local",
            "tool_name": "read",
            "argument_hash": hash_arguments(ARGS),
            "result_status": "success",
        },
    )


@pytest.mark.parametrize("tool", ["write", "unclassified", "unknown"])
async def test_context_rejects_tools_before_launch(
    config: MCPServerConfig, audit: AsyncMock, transport: tuple[FakeServer, AsyncMock], tool: str
) -> None:
    with pytest.raises(MCPPermissionError):
        await make_adapter(config, audit).retrieve_context("local", tool, ARGS)
    transport[1].assert_not_awaited()
    assert audit.log_event.call_args.kwargs["payload"]["result_status"] == "denied"


@pytest.mark.parametrize("server", ["local", "unconfigured"])
async def test_context_rejects_disabled_and_unknown_servers(
    config: MCPServerConfig, audit: AsyncMock, transport: tuple[FakeServer, AsyncMock], server: str
) -> None:
    config.enabled = False
    with pytest.raises(MCPServerNotFoundError):
        await make_adapter(config, audit).retrieve_context(server, "read", ARGS)
    transport[1].assert_not_awaited()


async def test_context_rejects_wildcard_only_allowlist(
    config: MCPServerConfig, audit: AsyncMock, transport: tuple[FakeServer, AsyncMock]
) -> None:
    config.allowed_tools = ["*"]
    adapter = make_adapter(config, audit)
    with pytest.raises(MCPPermissionError):
        await adapter.list_tools("local")
    with pytest.raises(MCPPermissionError):
        await adapter.retrieve_context("local", "read", ARGS)
    transport[1].assert_not_awaited()


@pytest.mark.parametrize(
    "arguments",
    [{}, {"query": 12}, {"query": float("nan")}, {"query": "x" * 65536}],
    ids=["missing", "wrong-type", "not-json", "over-limit"],
)
async def test_context_rejects_invalid_arguments_before_launch(
    config: MCPServerConfig,
    audit: AsyncMock,
    transport: tuple[FakeServer, AsyncMock],
    arguments: dict[str, object],
) -> None:
    with pytest.raises(MCPToolSchemaError):
        await make_adapter(config, audit).retrieve_context("local", "read", arguments)
    transport[1].assert_not_awaited()
    assert audit.log_event.call_args.kwargs["payload"]["result_status"] == "invalid_arguments"


async def test_missing_schema_is_configurable(
    config: MCPServerConfig, audit: AsyncMock, transport: tuple[FakeServer, AsyncMock]
) -> None:
    config.tool_schemas.clear()
    strict = make_adapter(config, audit, MCP_STRICT_SCHEMA_VALIDATION=True)
    with pytest.raises(MCPToolSchemaError):
        await strict.retrieve_context("local", "read", ARGS)
    transport[1].assert_not_awaited()
    assert (await make_adapter(config, audit).retrieve_context("local", "read", ARGS)).content


async def test_schema_does_not_retrieve_remote_references(
    config: MCPServerConfig, audit: AsyncMock, transport: tuple[FakeServer, AsyncMock]
) -> None:
    config.tool_schemas["read"] = {"$ref": "https://schema.invalid/external"}
    with pytest.raises(MCPToolSchemaError):
        await make_adapter(config, audit).retrieve_context("local", "read", ARGS)
    transport[1].assert_not_awaited()


@pytest.mark.parametrize("outcome", ["invalid", "stall"])
async def test_optional_context_failure_and_critical_failure(
    config: MCPServerConfig,
    audit: AsyncMock,
    transport: tuple[FakeServer, AsyncMock],
    outcome: str,
) -> None:
    transport[0].outcome = outcome
    adapter = make_adapter(config, audit)
    optional = await adapter.retrieve_context("local", "read", ARGS, required=False)
    assert optional.content == "" and not optional.required
    assert audit.log_event.call_args.kwargs["payload"]["result_status"] == (
        "timeout" if outcome == "stall" else "failed"
    )
    with pytest.raises(MCPContextFailureError) as failure:
        await adapter.retrieve_context("local", "read", ARGS)
    assert failure.value.code == "MCP_CONTEXT_FAILURE"
    assert transport[0].terminated


async def test_cancellation_audits_without_retaining_arguments(
    config: MCPServerConfig, audit: AsyncMock, transport: tuple[FakeServer, AsyncMock]
) -> None:
    process, _ = transport
    process.outcome = "stall"
    task = asyncio.create_task(make_adapter(config, audit).retrieve_context("local", "read", ARGS))
    async with asyncio.timeout(2):
        await process.tool_started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    payload = audit.log_event.call_args.kwargs["payload"]
    assert payload["result_status"] == "cancelled"
    assert payload["argument_hash"] == hash_arguments(ARGS)
    assert str(ARGS["query"]) not in str(payload)
    assert process.terminated


async def test_context_redacts_and_truncates_untrusted_text(
    config: MCPServerConfig, audit: AsyncMock, transport: tuple[FakeServer, AsyncMock]
) -> None:
    process, _ = transport
    process.tool_text = "private-token\x00\t" + ("x" * 100)
    adapter = make_adapter(config, audit, AI_MAX_PROMPT_TOKENS=5)
    chunk = await adapter.retrieve_context("local", "read", ARGS)
    assert chunk.content.startswith("[REDACTED]\t")
    assert len(chunk.content) == 20 and chunk.truncated
    assert "private-token" not in str(audit.log_event.call_args)
