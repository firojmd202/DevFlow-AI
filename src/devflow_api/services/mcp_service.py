"""Mandatory authorization gateway for MCP tool execution."""

import json
from datetime import UTC, datetime
from hashlib import sha256
from typing import cast
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from devflow_api.adapters.exceptions import (
    ConsumedError,
    MCPApprovalExpiredError,
    MCPApprovalRequiredError,
    MCPTimeoutError,
)
from devflow_api.adapters.mcp_client import MCPClient, MCPToolResult
from devflow_api.repositories.approval import AuditLogRepository
from devflow_api.repositories.mcp_approval import MCPApprovalRepository


def _validate_json(value: object) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("MCP argument keys must be strings")
            _validate_json(item)
    elif isinstance(value, list):
        for item in value:
            _validate_json(item)
    elif value is not None and type(value) not in (bool, int, float, str):
        raise ValueError("MCP arguments must contain only JSON values")


def _canonical_arguments(arguments: dict[str, object]) -> str:
    _validate_json(arguments)
    return json.dumps(arguments, sort_keys=True, separators=(",", ":"), allow_nan=False)


def hash_arguments(arguments: dict[str, object]) -> str:
    return sha256(_canonical_arguments(arguments).encode("utf-8")).hexdigest()


class MCPService:
    def __init__(
        self,
        mcp_client: MCPClient,
        audit_repo: AuditLogRepository,
        mcp_approval_repo: MCPApprovalRepository,
    ) -> None:
        self._client = mcp_client
        self._audit = audit_repo
        self._approvals = mcp_approval_repo

    async def invoke_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, object],
        actor_id: str,
        mcp_approval_id: UUID | None = None,
        trusted_workflow_run_id: int | None = None,
    ) -> MCPToolResult:
        config = self._client._configured_tool(server_name, tool_name)
        classification = config.tool_classifications.get(tool_name, "unknown")
        canonical = _canonical_arguments(arguments)
        snapshot = cast(dict[str, object], json.loads(canonical))
        arguments_hash = sha256(canonical.encode("utf-8")).hexdigest()
        details: dict[str, object] = {
            "server": server_name,
            "tool": tool_name,
            "mcp_approval_id": str(mcp_approval_id) if isinstance(mcp_approval_id, UUID) else None,
        }

        async def audit(event: str, *, actor: str = "system", **extra: object) -> None:
            await self._audit.log_event(event, actor, trusted_workflow_run_id, details | extra)

        async def reject(reason: str) -> None:
            await audit("mcp_approval_rejected", reason=reason)

        async def on_launch() -> None:
            await audit("mcp_tool_invoked", arg_keys=list(snapshot))

        if classification != "read_only":
            required = MCPApprovalRequiredError(server_name, tool_name, classification)
            try:
                approval = (
                    await self._approvals.get_by_id(mcp_approval_id)
                    if isinstance(mcp_approval_id, UUID)
                    else None
                )
            except SQLAlchemyError:
                raise required from None
            if approval is None:
                await audit("mcp_approval_missing")
                await audit("mcp_approval_requested")
                raise required
            if approval.status == "EXPIRED" or approval.expires_at <= datetime.now(UTC):
                await audit("mcp_approval_expired")
                raise MCPApprovalExpiredError(server_name, tool_name)
            if approval.status == "REJECTED":
                await audit("mcp_approval_denied", actor="user")
                raise required
            if approval.status != "APPROVED" or approval.consumed_at is not None:
                if approval.status == "CONSUMED" or approval.consumed_at is not None:
                    await reject("already_consumed")
                else:
                    await audit("mcp_approval_requested")
                raise required
            if (
                approval.mcp_server_id,
                approval.tool_name,
                approval.arguments_hash,
                approval.actor_id,
            ) != (server_name, tool_name, arguments_hash, actor_id):
                await reject("mismatched_binding")
                raise required
            if approval.workflow_run_id != trusted_workflow_run_id:
                if approval.workflow_run_id is None:
                    reason = "unexpected_workflow_context"
                elif trusted_workflow_run_id is None:
                    reason = "missing_workflow_context"
                else:
                    reason = "workflow_run_mismatch"
                await reject(reason)
                raise required
            if not isinstance(mcp_approval_id, UUID):
                raise required
            try:
                await self._approvals.consume_atomic(
                    mcp_approval_id,
                    actor_id,
                    server_name,
                    tool_name,
                    arguments_hash,
                    trusted_workflow_run_id,
                    datetime.now(UTC),
                )
            except ConsumedError as exc:
                # The database may be unavailable. Never attempt a launch even if auditing fails.
                try:
                    await reject(exc.reason)
                except SQLAlchemyError:
                    raise required from None
                raise required from None
            await audit("mcp_approval_granted")

        try:
            async with self._client._authorized(server_name, tool_name, snapshot, on_launch):
                result = await self._client.call_tool(server_name, tool_name, snapshot)
        except BaseException as exc:
            await audit("mcp_tool_failed", indeterminate=isinstance(exc, MCPTimeoutError))
            raise
        if result.is_error:
            await audit("mcp_tool_failed", indeterminate=False)
        else:
            await audit("mcp_tool_completed")
        return result
