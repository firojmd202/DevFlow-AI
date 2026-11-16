"""Explicit-env subprocess transport for the MCP SDK."""

import asyncio
import os
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Final

import anyio
from mcp import ClientSession
from mcp.shared.message import SessionMessage
from mcp.types import JSONRPCMessage, LoggingMessageNotificationParams
from pydantic import BaseModel, SecretStr

from devflow_api.adapters.exceptions import (
    MCPConnectionError,
    MCPPermissionError,
    MCPSecretResolutionError,
    MCPServerNotFoundError,
    MCPTimeoutError,
)
from devflow_core.config import Settings, get_settings
from devflow_core.mcp_config import MCPServerConfig

__all__ = ["MCPClient", "MCPServerConfig", "MCPToolResult"]

_WINDOWS_ENV: Final = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATHEXT", "COMSPEC")
_POSIX_ENV: Final = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR")
_SECRET = re.compile(r"\$\{([^{}]*)\}")
type LaunchHook = Callable[[], Awaitable[None]]


class MCPToolResult(BaseModel):
    content: list[dict[str, object]]
    is_error: bool = False
    stub: bool = False


def _resolve_env(config: MCPServerConfig, settings: Settings) -> dict[str, str]:
    system_names = _WINDOWS_ENV if os.name == "nt" else _POSIX_ENV
    env = {name: os.environ[name] for name in system_names if name in os.environ}

    def replace(match: re.Match[str]) -> str:
        secret_name = match[1].upper()
        value = getattr(settings, secret_name, None)
        if not isinstance(value, SecretStr):
            raise MCPSecretResolutionError(secret_name)
        return value.get_secret_value()

    for name, value in config.env.items():
        key = name.upper() if os.name == "nt" else name
        env[key] = _SECRET.sub(replace, value)
    return env


async def _discard_server_log(params: LoggingMessageNotificationParams) -> None:
    """Server log payloads may contain credentials or tool arguments."""


@asynccontextmanager
async def _stdio_session(process: asyncio.subprocess.Process) -> AsyncIterator[ClientSession]:
    stdout, stdin = process.stdout, process.stdin
    if stdout is None or stdin is None:
        raise MCPConnectionError("MCP stdio pipes unavailable")
    inbound, read = anyio.create_memory_object_stream[SessionMessage | Exception](0)
    write, outbound = anyio.create_memory_object_stream[SessionMessage](0)

    async def read_stdout() -> None:
        async with inbound:
            while line := await stdout.readline():
                message = JSONRPCMessage.model_validate_json(line)
                await inbound.send(SessionMessage(message))

    async def write_stdin() -> None:
        async with outbound:
            async for item in outbound:
                document = item.message.model_dump_json(by_alias=True, exclude_none=True)
                stdin.write((document + "\n").encode("utf-8"))
                await stdin.drain()

    async with read, write, anyio.create_task_group() as tasks:
        tasks.start_soon(read_stdout)
        tasks.start_soon(write_stdin)
        try:
            async with ClientSession(read, write, logging_callback=_discard_server_log) as session:
                yield session
        finally:
            tasks.cancel_scope.cancel()


async def _stop_process(process: asyncio.subprocess.Process) -> None:
    if process.stdin is not None:
        process.stdin.close()
    if process.returncode is None:
        try:
            process.terminate()
        except ProcessLookupError:
            pass
    # Drain pipes during shutdown so a server writing to stdout cannot stall wait().
    reaper = asyncio.create_task(process.communicate())
    try:
        await asyncio.wait_for(asyncio.shield(reaper), timeout=5.0)
    except TimeoutError:
        try:
            process.kill()
        except ProcessLookupError:
            pass
        await reaper


class MCPClient:
    def __init__(self, configs: list[MCPServerConfig], settings: Settings | None = None) -> None:
        self._configs = {config.name: config.model_copy(deep=True) for config in configs}
        self._settings = settings if settings is not None else get_settings()
        self._authorization: ContextVar[tuple[str, str, dict[str, object], LaunchHook] | None] = (
            ContextVar("mcp_invocation", default=None)
        )

    def _configured_tool(self, server_name: str, tool_name: str) -> MCPServerConfig:
        config = self._configs.get(server_name)
        if config is None or not config.enabled:
            raise MCPServerNotFoundError(server_name)
        if "*" not in config.allowed_tools and tool_name not in config.allowed_tools:
            raise MCPPermissionError(server_name, tool_name)
        return config

    @asynccontextmanager
    async def _authorized(
        self, server_name: str, tool_name: str, arguments: dict[str, object], on_launch: LaunchHook
    ) -> AsyncIterator[None]:
        token = self._authorization.set((server_name, tool_name, arguments, on_launch))
        try:
            yield
        finally:
            self._authorization.reset(token)

    async def call_tool(
        self, server_name: str, tool_name: str, arguments: dict[str, object]
    ) -> MCPToolResult:
        config = self._configured_tool(server_name, tool_name)
        grant = self._authorization.get()
        if grant is None or grant[:2] != (server_name, tool_name) or grant[2] is not arguments:
            raise MCPPermissionError(server_name, tool_name)
        self._authorization.set(None)
        env = _resolve_env(config, self._settings)

        process: asyncio.subprocess.Process | None = None
        try:
            async with asyncio.timeout(config.timeout_seconds):
                process = await asyncio.create_subprocess_exec(
                    *config.command,
                    *config.args,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                    env=env,
                )
                await grant[3]()
                async with _stdio_session(process) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments=arguments)
        except TimeoutError:
            raise MCPTimeoutError(server_name, tool_name, config.timeout_seconds) from None
        except Exception:
            raise MCPConnectionError(server_name, "MCP invocation failed") from None
        finally:
            if process is not None:
                cleanup = asyncio.create_task(_stop_process(process))
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    await asyncio.shield(cleanup)
                    raise

        return MCPToolResult(
            content=[item.model_dump(mode="json", by_alias=True) for item in result.content],
            is_error=result.isError,
        )
