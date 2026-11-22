"""Read-only Wave 2 context retrieval over MCPClient, verified with MCP SDK 2.3.0."""

import asyncio
import json
from hashlib import sha256
from typing import cast

from jsonschema.validators import validator_for  # type: ignore[import-untyped]
from referencing import Registry

from devflow_api.adapters.exceptions import (
    MCPConnectionError,
    MCPContextFailureError,
    MCPPermissionError,
    MCPSecretResolutionError,
    MCPServerNotFoundError,
    MCPTimeoutError,
    MCPToolSchemaError,
)
from devflow_api.adapters.mcp_client import MCPClient
from devflow_api.repositories.approval import AuditLogRepository
from devflow_api.schemas.mcp import ContextChunk
from devflow_core.config import Settings, get_settings
from devflow_core.logging import get_logger
from devflow_core.mcp_arguments import canonical_arguments

_MAX_ARGUMENT_BYTES = 64 * 1024
_CONTROL_CHARACTERS = dict.fromkeys((set(range(32)) | set(range(127, 160))) - {9, 10})


async def _on_launch() -> None:
    """MCPClient requires a launch hook. This adapter audits the final result."""


class MCPClientAdapter:
    """Validate operator schemas and pass only approved read-only context tools."""

    def __init__(
        self, client: MCPClient, audit: AuditLogRepository, settings: Settings | None = None
    ) -> None:
        self._client = client
        self._audit = audit
        self._settings = settings if settings is not None else get_settings()

    async def list_tools(self, server_name: str) -> tuple[str, ...]:
        return await self._client.list_tools(server_name)

    async def retrieve_context(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, object],
        *,
        required: bool = True,
        specification_request_id: int | None = None,
        workflow_run_id: int | None = None,
    ) -> ContextChunk:
        status = "failed"
        argument_hash = None
        audit_server = audit_tool = None
        try:
            try:
                canonical = canonical_arguments(arguments).encode("utf-8")
            except (ValueError, RecursionError):
                canonical = b""
            if canonical and len(canonical) <= _MAX_ARGUMENT_BYTES:
                argument_hash = sha256(canonical).hexdigest()
            safe = self._client._redactor()
            self._client._configured_server(server_name)
            audit_server = safe(None, "info", {"value": server_name})["value"]
            config = self._client._configured_tool(server_name, tool_name)
            if (
                tool_name == "*"
                or tool_name not in config.allowed_tools
                or config.tool_classifications.get(tool_name) != "read_only"
            ):
                raise MCPPermissionError(server_name, tool_name)
            safe = self._client._redactor(config)
            audit_server = safe(None, "info", {"value": server_name})["value"]
            audit_tool = safe(None, "info", {"value": tool_name})["value"]
            if argument_hash is None:
                raise MCPToolSchemaError()
            snapshot = cast(dict[str, object], json.loads(canonical))
            self._validate_schema(config.tool_schemas.get(tool_name), snapshot)
            async with self._client._authorized(server_name, tool_name, snapshot, _on_launch):
                result = await self._client.call_tool(server_name, tool_name, snapshot)
            if result.is_error or result.stub:
                raise MCPContextFailureError()
            text = "\n".join(
                value
                for item in result.content
                if item.get("type") == "text" and isinstance(value := item.get("text"), str)
            )
            safe_text = str(safe(None, "info", {"value": text})["value"]).translate(
                _CONTROL_CHARACTERS
            )
            limit = self._settings.AI_MAX_PROMPT_TOKENS * 4
            status = "success"
            return ContextChunk(
                content=safe_text[:limit],
                server=server_name,
                tool=tool_name,
                required=required,
                truncated=len(safe_text) > limit,
            )
        except (MCPServerNotFoundError, MCPPermissionError):
            status = "denied"
            raise
        except MCPToolSchemaError:
            status = "invalid_arguments"
            raise
        except asyncio.CancelledError:
            status = "cancelled"
            raise
        except (
            MCPConnectionError,
            MCPContextFailureError,
            MCPSecretResolutionError,
            MCPTimeoutError,
        ) as exc:
            status = "timeout" if isinstance(exc, MCPTimeoutError) else "failed"
            if required:
                raise MCPContextFailureError() from None
            get_logger(__name__).warning("Optional MCP context unavailable", result_status=status)
            return ContextChunk(
                content="", server=server_name, tool=tool_name, required=False, truncated=False
            )
        finally:
            payload: dict[str, object] = {
                "server_name": audit_server,
                "tool_name": audit_tool,
                "argument_hash": argument_hash,
                "result_status": status,
            }
            if specification_request_id is not None:
                payload["specification_request_id"] = specification_request_id
            if workflow_run_id is None:
                await self._audit.log_event("mcp_tool_invoked", "system", payload=payload)
            else:
                await self._audit.log_event(
                    "mcp_tool_invoked", "system", workflow_run_id, payload=payload
                )

    def _validate_schema(
        self, schema: dict[str, object] | None, arguments: dict[str, object]
    ) -> None:
        if schema is None:
            if self._settings.MCP_STRICT_SCHEMA_VALIDATION:
                raise MCPToolSchemaError()
            return
        try:
            validator = validator_for(schema)
            validator.check_schema(schema)
            # An empty registry supports local references without retrieving remote resources.
            validator(schema, registry=Registry()).validate(arguments)
        except Exception:
            raise MCPToolSchemaError() from None
