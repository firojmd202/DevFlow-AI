"""Offline subprocess and SDK stream tests."""

import asyncio
import os
from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr

from devflow_api.adapters.exceptions import (
    MCPConnectionError,
    MCPPermissionError,
    MCPSecretResolutionError,
    MCPTimeoutError,
)
from devflow_api.adapters.mcp_client import MCPClient, MCPServerConfig, MCPToolResult
from devflow_core.config import Settings
from tests.mcp_fakes import FakeServer


@pytest.fixture
def mcp_client() -> MCPClient:
    return MCPClient(
        [
            MCPServerConfig(
                name="configured",
                command=["server"],
                timeout_seconds=1,
                allowed_tools=["read"],
                env={"EXPLICIT": "${GITHUB_TOKEN}"},
            )
        ],
        Settings(GITHUB_TOKEN=SecretStr("test-value")),
    )


@pytest.fixture
async def fake_spawn(monkeypatch: pytest.MonkeyPatch) -> tuple[FakeServer, AsyncMock]:
    process = FakeServer()
    spawn = AsyncMock(return_value=process)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    return process, spawn


async def invoke(client: MCPClient, arguments: dict[str, object] | None = None) -> MCPToolResult:
    args = {} if arguments is None else arguments
    async with client._authorized("configured", "read", args, AsyncMock()):
        return await client.call_tool("configured", "read", args)


async def test_mcp_call_tool_returns_result(
    mcp_client: MCPClient, fake_spawn: tuple[FakeServer, AsyncMock]
) -> None:
    args: dict[str, object] = {"null": None, "nested": {"x": [1, False]}}
    result = await invoke(mcp_client, args)
    assert result.content == [
        {"type": "text", "text": "result", "annotations": None, "_meta": None}
    ]
    assert not result.stub and not result.is_error
    assert fake_spawn[0].arguments == args


async def test_mcp_subprocess_receives_explicit_env(
    mcp_client: MCPClient, fake_spawn: tuple[FakeServer, AsyncMock]
) -> None:
    assert not (await invoke(mcp_client)).stub
    names = (
        ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATHEXT", "COMSPEC")
        if os.name == "nt"
        else ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR")
    )
    expected = {name: os.environ[name] for name in names if name in os.environ}
    expected["EXPLICIT"] = "test-value"
    assert fake_spawn[1].call_args.kwargs["env"] == expected
    assert fake_spawn[1].call_args.args == ("server",)


async def test_mcp_subprocess_launched_with_explicit_env(
    mcp_client: MCPClient, fake_spawn: tuple[FakeServer, AsyncMock]
) -> None:
    await invoke(mcp_client)
    assert fake_spawn[1].call_args.kwargs["env"]["EXPLICIT"] == "test-value"


async def test_mcp_subprocess_does_not_inherit_parent_secrets(
    mcp_client: MCPClient,
    fake_spawn: tuple[FakeServer, AsyncMock],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PARENT_ONLY_SECRET", "private")
    await invoke(mcp_client)
    assert "PARENT_ONLY_SECRET" not in fake_spawn[1].call_args.kwargs["env"]


async def test_mcp_secret_values_not_in_log_records(
    mcp_client: MCPClient,
    fake_spawn: tuple[FakeServer, AsyncMock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    await invoke(mcp_client, {"value": "argument-secret"})
    assert "test-value" not in caplog.text and "argument-secret" not in caplog.text
    assert fake_spawn[1].call_args.kwargs["env"]["EXPLICIT"] == "test-value"


async def test_mcp_permission_denied_before_subprocess(
    mcp_client: MCPClient, fake_spawn: tuple[FakeServer, AsyncMock]
) -> None:
    with pytest.raises(MCPPermissionError):
        await mcp_client.call_tool("configured", "blocked", {})
    fake_spawn[1].assert_not_awaited()


async def test_unknown_secret_rejected_before_subprocess(
    fake_spawn: tuple[FakeServer, AsyncMock],
) -> None:
    client = MCPClient(
        [MCPServerConfig(name="configured", command=["server"], env={"TOKEN": "${MISSING}"})]
    )
    with pytest.raises(MCPSecretResolutionError):
        await invoke(client)
    fake_spawn[1].assert_not_awaited()


@pytest.mark.parametrize("outcome", ["success", "invalid"])
async def test_mcp_subprocess_cleanup_in_finally_block(
    mcp_client: MCPClient, fake_spawn: tuple[FakeServer, AsyncMock], outcome: str
) -> None:
    process, _ = fake_spawn
    process.outcome = outcome
    if outcome == "invalid":
        with pytest.raises(MCPConnectionError):
            await invoke(mcp_client)
    else:
        await invoke(mcp_client)
    assert process.terminated and process.returncode == 0
    process.stdin.close.assert_called_once()


async def test_mcp_subprocess_terminated_on_timeout(
    mcp_client: MCPClient,
    fake_spawn: tuple[FakeServer, AsyncMock],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process, _ = fake_spawn
    process.outcome = "timeout"

    async def grace(task: asyncio.Future[tuple[bytes, bytes]], timeout: float) -> None:
        assert timeout == 5.0
        task.cancel()
        raise TimeoutError

    monkeypatch.setattr(asyncio, "wait_for", grace)
    with pytest.raises(MCPTimeoutError):
        await invoke(mcp_client)
    assert process.terminated and process.killed and process.returncode == -9
