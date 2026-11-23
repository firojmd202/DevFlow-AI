"""Explicit-env subprocess transport for the MCP SDK."""

import asyncio
import logging
import os
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Final

import anyio
from mcp import ClientSession
from mcp.shared.message import SessionMessage
from mcp.types import (
    CallToolResult,
    JSONRPCMessage,
    JSONRPCResponse,
    LoggingMessageNotificationParams,
    PaginatedRequestParams,
)
from pydantic import BaseModel, SecretStr, TypeAdapter

from devflow_api.adapters.exceptions import (
    MCPConnectionError,
    MCPPermissionError,
    MCPSecretResolutionError,
    MCPServerNotFoundError,
    MCPTimeoutError,
)
from devflow_core.config import Settings, get_settings
from devflow_core.logging import RedactSecretsProcessor
from devflow_core.mcp_config import MCPServerConfig

__all__ = ["MCPClient", "MCPServerConfig", "MCPToolResult"]

_WINDOWS_ENV: Final = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATHEXT", "COMSPEC")
_POSIX_ENV: Final = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR")
_SECRET = re.compile(r"\$\{([^{}]*)\}")
_MESSAGES = TypeAdapter[JSONRPCMessage](JSONRPCMessage)
type LaunchHook = Callable[[], Awaitable[None]]

# SDK diagnostics can include untrusted protocol fields and validation tracebacks.
# The application records sanitized outcomes at the invocation boundary.
for _logger_name in ("mcp.client.session", "mcp.shared.jsonrpc_dispatcher"):
    logging.getLogger(_logger_name).addFilter(lambda _: False)


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
                message = _MESSAGES.validate_json(line)
                # Legacy stdio negotiation can strip newer result tags before the SDK
                # validates the result. Reject an explicit unsupported tag at the wire.
                if (
                    isinstance(message, JSONRPCResponse)
                    and message.result.get("resultType", "complete") != "complete"
                ):
                    raise MCPConnectionError("stdio", "Unsupported MCP result variant")
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

    def _redactor(self, config: MCPServerConfig | None = None) -> RedactSecretsProcessor:
        secrets = tuple(
            value.get_secret_value()
            for name in type(self._settings).model_fields
            if isinstance(value := getattr(self._settings, name), SecretStr)
        )
        if config is not None:
            resolved = _resolve_env(config, self._settings)
            secrets += tuple(
                resolved[key.upper() if os.name == "nt" else key] for key in config.env
            )
        return RedactSecretsProcessor(secrets)

    def _configured_server(self, server_name: str) -> MCPServerConfig:
        config = self._configs.get(server_name)
        if config is None or not config.enabled:
            raise MCPServerNotFoundError(server_name)
        return config

    def _configured_tool(self, server_name: str, tool_name: str) -> MCPServerConfig:
        config = self._configured_server(server_name)
        if "*" not in config.allowed_tools and tool_name not in config.allowed_tools:
            raise MCPPermissionError(server_name, tool_name)
        return config

    async def list_tools(self, server_name: str) -> tuple[str, ...]:
        """Discover explicitly allowed read-only tool names for context retrieval."""
        config = self._configured_server(server_name)
        allowed = {
            name
            for name, classification in config.tool_classifications.items()
            if classification == "read_only" and name in config.allowed_tools and name != "*"
        }
        if not allowed:
            raise MCPPermissionError(server_name)
        discovered: set[str] = set()
        seen_cursors: set[str] = set()
        params = None
        async with self._session(config, "") as session:
            for _ in range(16):
                result = await session.list_tools(params=params)
                if result.result_type != "complete":
                    break
                discovered.update(tool.name for tool in result.tools if tool.name in allowed)
                cursor = result.next_cursor
                if cursor is None or discovered == allowed:
                    return tuple(sorted(discovered))
                if cursor in seen_cursors:
                    break
                seen_cursors.add(cursor)
                params = PaginatedRequestParams(cursor=cursor)
            raise MCPConnectionError(server_name, "Invalid MCP tool discovery response")

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
        async with self._session(config, tool_name, grant[3]) as session:
            result: object = await session.call_tool(tool_name, arguments=arguments)
            if not isinstance(result, CallToolResult) or result.result_type != "complete":
                raise MCPConnectionError(server_name, "Unexpected MCP tool result")
            return MCPToolResult(
                content=[item.model_dump(mode="json", by_alias=True) for item in result.content],
                is_error=result.is_error,
            )

    @asynccontextmanager
    async def _session(
        self, config: MCPServerConfig, tool_name: str, on_launch: LaunchHook | None = None
    ) -> AsyncIterator[ClientSession]:
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
                if on_launch is not None:
                    await on_launch()
                async with _stdio_session(process) as session:
                    initialized = await session.initialize()
                    if initialized.capabilities.tools is None:
                        raise MCPConnectionError(config.name, "MCP tools capability unavailable")
                    yield session
        except TimeoutError:
            raise MCPTimeoutError(config.name, tool_name, config.timeout_seconds) from None
        except Exception:
            raise MCPConnectionError(config.name, "MCP invocation failed") from None
        finally:
            if process is not None:
                cleanup = asyncio.create_task(_stop_process(process))
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    await asyncio.shield(cleanup)
                    raise
