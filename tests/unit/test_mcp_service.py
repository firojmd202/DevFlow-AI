"""Offline MCP authorization, replay and concurrency tests."""

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib.metadata import version
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from devflow_api.adapters.exceptions import (
    ConsumedError,
    MCPApprovalExpiredError,
    MCPApprovalRequiredError,
    MCPConnectionError,
    MCPPermissionError,
    MCPTimeoutError,
)
from devflow_api.adapters.mcp_client import MCPClient, MCPServerConfig, MCPToolResult
from devflow_api.database import _configure_sqlite
from devflow_api.models import Base, MCPApproval, Workflow, WorkflowRun
from devflow_api.repositories.approval import AuditLogRepository
from devflow_api.repositories.mcp_approval import MCPApprovalRepository
from devflow_api.services.mcp_service import MCPService, hash_arguments
from tests.mcp_fakes import FakeServer

ARGS: dict[str, object] = {"path": "local"}


@dataclass
class Scope:
    client: MCPClient
    session: AsyncSession
    sessions: async_sessionmaker[AsyncSession]
    repository: MCPApprovalRepository
    service: MCPService
    call: AsyncMock

    async def seed(self, **fields: object) -> UUID:
        row = MCPApproval(
            **(
                {
                    "id": str(uuid4()),
                    "mcp_server_id": "server",
                    "tool_name": "write",
                    "arguments_hash": hash_arguments(ARGS),
                    "actor_id": "actor",
                    "status": "APPROVED",
                    "requested_at": datetime.now(UTC),
                    "expires_at": datetime.now(UTC) + timedelta(minutes=5),
                }
                | fields
            )
        )
        await self.repository.create(row)
        return UUID(row.id)

    async def run_id(self) -> int:
        workflow = Workflow(name="Workflow")
        self.session.add(workflow)
        await self.session.flush()
        run = WorkflowRun(workflow_id=workflow.id)
        self.session.add(run)
        await self.session.commit()
        return run.id

    async def invoke(
        self,
        id: UUID | None = None,
        *,
        tool: str = "write",
        args: dict[str, object] | None = None,
        context: int | None = None,
    ) -> MCPToolResult:
        return await self.service.invoke_tool(
            "server", tool, ARGS if args is None else args, "actor", id, context
        )

    async def denied(
        self,
        id: UUID | None = None,
        *,
        tool: str = "write",
        args: dict[str, object] | None = None,
        context: int | None = None,
    ) -> None:
        with pytest.raises(MCPApprovalRequiredError):
            await self.invoke(id, tool=tool, args=args, context=context)
        self.call.assert_not_awaited()

    async def events(self, run_id: int | None = None) -> list[tuple[str, object]]:
        repo = AuditLogRepository(self.session)
        rows = await repo.list_for_run(run_id) if run_id is not None else await repo.list()
        return [(row.event_type, json.loads(row.payload_json or "{}")) for row in rows]

    async def status(self, id: UUID) -> str:
        row = await self.repository.get_by_id(id)
        assert row is not None
        return row.status

    async def consume(self, id: UUID) -> MCPApproval:
        return await self.repository.consume_atomic(
            id, "actor", "server", "write", hash_arguments(ARGS), None, datetime.now(UTC)
        )


@pytest.fixture
async def mcp_scope(sqlite_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Scope]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{sqlite_path.as_posix()}")
    event.listen(engine.sync_engine, "connect", _configure_sqlite)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    client = MCPClient(
        [
            MCPServerConfig(
                name="server",
                command=["server"],
                tool_classifications={"read": "read_only", "write": "consequential"},
            )
        ]
    )
    call = AsyncMock(return_value=MCPToolResult(content=[]))
    monkeypatch.setattr(client, "call_tool", call)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            repo = MCPApprovalRepository(session)
            service = MCPService(client, AuditLogRepository(session), repo)
            yield Scope(client, session, sessions, repo, service, call)
    finally:
        await engine.dispose()


async def test_forged_approval_record_rejected(mcp_scope: Scope) -> None:
    approval = MCPApproval(status="APPROVED")
    with pytest.raises(TypeError):
        await mcp_scope.service.invoke_tool(
            "server", "write", ARGS, "actor", approval_record=approval
        )  # type: ignore[call-arg]
    await mcp_scope.denied(uuid4())


async def test_expired_approval_rejected_at_invocation(mcp_scope: Scope) -> None:
    id = await mcp_scope.seed(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    with pytest.raises(MCPApprovalExpiredError):
        await mcp_scope.invoke(id)
    mcp_scope.call.assert_not_awaited()


async def test_mismatched_tool_name_rejected(mcp_scope: Scope) -> None:
    await mcp_scope.denied(await mcp_scope.seed(tool_name="other"))


async def test_mismatched_arguments_hash_rejected(mcp_scope: Scope) -> None:
    await mcp_scope.denied(await mcp_scope.seed(), args={"path": "other"})


@pytest.mark.parametrize("field", ["actor_id", "mcp_server_id"])
async def test_other_mismatched_bindings(mcp_scope: Scope, field: str) -> None:
    id = await mcp_scope.seed(**{field: "other"})
    await mcp_scope.denied(id)
    assert await mcp_scope.status(id) == "APPROVED"


async def test_replay_after_consumption_rejected(mcp_scope: Scope) -> None:
    id = await mcp_scope.seed()
    await mcp_scope.invoke(id)
    with pytest.raises(MCPApprovalRequiredError):
        await mcp_scope.invoke(id)
    assert mcp_scope.call.await_count == 1


async def test_concurrent_consumption_safe(mcp_scope: Scope) -> None:
    id = await mcp_scope.seed()
    async with mcp_scope.sessions() as session:
        service = MCPService(
            mcp_scope.client, AuditLogRepository(session), MCPApprovalRepository(session)
        )
        outcomes = await asyncio.gather(
            mcp_scope.invoke(id),
            service.invoke_tool("server", "write", ARGS, "actor", id),
            return_exceptions=True,
        )
    assert sum(isinstance(item, MCPToolResult) for item in outcomes) == 1
    assert sum(isinstance(item, MCPApprovalRequiredError) for item in outcomes) == 1
    assert mcp_scope.call.await_count == 1


async def test_read_only_tool_no_approval_required(mcp_scope: Scope) -> None:
    assert not (await mcp_scope.invoke(tool="read")).stub
    mcp_scope.call.assert_awaited_once()


async def test_no_direct_mcp_client_bypass() -> None:
    from devflow_api.adapters.live.mcp_live import MCPLiveAdapter
    from devflow_core.config import Settings

    with pytest.raises(MCPPermissionError):
        await MCPLiveAdapter(Settings()).call_tool("server", "write", ARGS)


async def binding_error(
    scope: Scope,
    bound: int | None,
    trusted: int | None,
    expected: str,
    args: dict[str, object] | None = None,
) -> None:
    id = await scope.seed(workflow_run_id=bound, arguments_hash=hash_arguments(args or ARGS))
    await scope.denied(id, args=args, context=trusted)
    assert await scope.status(id) == "APPROVED"
    assert any(
        event == "mcp_approval_rejected"
        and isinstance(payload, dict)
        and payload["reason"] == expected
        for event, payload in await scope.events(trusted)
    )


async def test_approval_wrong_workflow_run_rejected(mcp_scope: Scope) -> None:
    await binding_error(
        mcp_scope, await mcp_scope.run_id(), await mcp_scope.run_id(), "workflow_run_mismatch"
    )


async def test_approval_bound_to_workflow_rejected_without_workflow_context(
    mcp_scope: Scope,
) -> None:
    await binding_error(mcp_scope, await mcp_scope.run_id(), None, "missing_workflow_context")


async def test_approval_unbound_rejected_with_workflow_context(mcp_scope: Scope) -> None:
    await binding_error(mcp_scope, None, await mcp_scope.run_id(), "unexpected_workflow_context")


async def test_workflow_run_id_from_arguments_not_trusted(mcp_scope: Scope) -> None:
    run_id = await mcp_scope.run_id()
    await binding_error(
        mcp_scope, run_id, None, "missing_workflow_context", args={"workflow_run_id": run_id}
    )


async def test_concurrent_consumption_only_one_succeeds(mcp_scope: Scope) -> None:
    id = await mcp_scope.seed()
    async with mcp_scope.sessions() as session:
        rival = MCPApprovalRepository(session)
        outcomes = await asyncio.gather(
            mcp_scope.consume(id),
            rival.consume_atomic(
                id, "actor", "server", "write", hash_arguments(ARGS), None, datetime.now(UTC)
            ),
            return_exceptions=True,
        )
    assert sum(isinstance(item, MCPApproval) for item in outcomes) == 1
    assert sum(isinstance(item, ConsumedError) for item in outcomes) == 1


async def test_mcp_approval_consume_atomic_safe(mcp_scope: Scope) -> None:
    await test_concurrent_consumption_only_one_succeeds(mcp_scope)


async def alter_before_consume(
    scope: Scope, monkeypatch: pytest.MonkeyPatch, **fields: object
) -> None:
    id = await scope.seed()
    consume = scope.repository.consume_atomic

    async def changed(*args: object) -> MCPApproval:
        async with scope.sessions.begin() as writer:
            await writer.execute(
                update(MCPApproval).where(MCPApproval.id == str(id)).values(**fields)
            )
        return await consume(*args)  # type: ignore[arg-type]

    monkeypatch.setattr(scope.repository, "consume_atomic", changed)
    await scope.denied(id)
    assert await scope.status(id) != "CONSUMED"


async def test_expired_at_consumption_time_rejected(
    mcp_scope: Scope,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await alter_before_consume(
        mcp_scope, monkeypatch, expires_at=datetime.now(UTC) - timedelta(seconds=1)
    )


async def test_approval_modified_between_validation_and_consumption(
    mcp_scope: Scope,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await alter_before_consume(mcp_scope, monkeypatch, actor_id="changed")


async def test_consumed_approval_cannot_be_reused(mcp_scope: Scope) -> None:
    id = await mcp_scope.seed()
    assert (await mcp_scope.consume(id)).consumed_at is not None
    with pytest.raises(ConsumedError):
        await mcp_scope.consume(id)


async def failure_stays_consumed(scope: Scope, failure: Exception) -> UUID:
    id = await scope.seed()
    scope.call.side_effect = failure
    with pytest.raises(type(failure)):
        await scope.invoke(id)
    assert await scope.status(id) == "CONSUMED"
    assert (await scope.events())[-1][0] == "mcp_tool_failed"
    return id


async def test_execution_failure_does_not_restore_consumed_approval(mcp_scope: Scope) -> None:
    await failure_stays_consumed(mcp_scope, MCPConnectionError("server"))


async def test_execution_failure_does_not_restore_approval(mcp_scope: Scope) -> None:
    await failure_stays_consumed(mcp_scope, OSError("subprocess"))


async def test_timeout_recorded_as_indeterminate_in_audit(mcp_scope: Scope) -> None:
    await failure_stays_consumed(mcp_scope, MCPTimeoutError("server"))
    _, payload = (await mcp_scope.events())[-1]
    assert isinstance(payload, dict) and payload["indeterminate"] is True


async def test_new_approval_required_for_retry_after_failure(mcp_scope: Scope) -> None:
    id = await failure_stays_consumed(mcp_scope, OSError("subprocess"))
    mcp_scope.call.side_effect = None
    with pytest.raises(MCPApprovalRequiredError):
        await mcp_scope.invoke(id)
    await mcp_scope.invoke(await mcp_scope.seed())
    assert mcp_scope.call.await_count == 2


async def test_begin_immediate_prevents_toctou(mcp_scope: Scope) -> None:
    id = await mcp_scope.seed()
    bind = mcp_scope.session.bind
    assert bind is not None
    statements: list[str] = []

    def record(*args: object) -> None:
        statements.append(str(args[2]))

    event.listen(bind.sync_engine, "before_cursor_execute", record)
    try:
        await mcp_scope.consume(id)
    finally:
        event.remove(bind.sync_engine, "before_cursor_execute", record)
    assert statements[0] == "BEGIN IMMEDIATE"
    assert statements[1].startswith("SELECT") and statements[2].startswith("UPDATE")


async def test_busy_timeout_treated_as_authorization_failure(mcp_scope: Scope) -> None:
    id = await mcp_scope.seed()
    bind = mcp_scope.session.bind
    assert bind is not None
    async with mcp_scope.sessions() as lock:
        await lock.execute(text("BEGIN IMMEDIATE"))
        try:
            with pytest.raises(ConsumedError):
                await mcp_scope.consume(id)
        finally:
            await lock.rollback()
    assert await mcp_scope.status(id) == "APPROVED"
    mcp_scope.call.assert_not_awaited()


async def test_unknown_tool_denied_without_approval(mcp_scope: Scope) -> None:
    await mcp_scope.denied(tool="unclassified")


async def test_consequential_tool_denied_without_approval(mcp_scope: Scope) -> None:
    await mcp_scope.denied()


async def test_read_only_tool_permitted_without_approval(mcp_scope: Scope) -> None:
    await mcp_scope.invoke(tool="read")
    assert [event for event, _ in await mcp_scope.events()] == ["mcp_tool_completed"]


async def test_direct_mcp_client_call_blocked_without_service_layer() -> None:
    client = MCPClient([MCPServerConfig(name="server", command=["server"])])
    with pytest.raises(MCPPermissionError):
        await client.call_tool("server", "write", ARGS)


async def test_expired_mcp_approval_rejected(mcp_scope: Scope) -> None:
    id = await mcp_scope.seed(status="EXPIRED")
    with pytest.raises(MCPApprovalExpiredError):
        await mcp_scope.invoke(id)


async def test_expired_mcp_approval_emits_approval_expired_event(mcp_scope: Scope) -> None:
    with pytest.raises(MCPApprovalExpiredError):
        await mcp_scope.invoke(await mcp_scope.seed(status="EXPIRED"))
    assert [event for event, _ in await mcp_scope.events()] == ["mcp_approval_expired"]


async def test_missing_approval_emits_approval_missing_event(mcp_scope: Scope) -> None:
    await mcp_scope.denied()
    assert [event for event, _ in await mcp_scope.events()] == [
        "mcp_approval_missing",
        "mcp_approval_requested",
    ]


async def test_allowlist_alone_insufficient_for_consequential_tool(mcp_scope: Scope) -> None:
    await mcp_scope.denied(await mcp_scope.seed(status="PENDING"))


def test_mcp_client_uses_locked_sdk_version() -> None:
    assert version("mcp").split(".")[0] == "2"


def test_hash_arguments_is_canonical() -> None:
    assert hash_arguments({"b": 2, "a": [1, None]}) == hash_arguments({"a": [1, None], "b": 2})
    assert hash_arguments({"a": True}) != hash_arguments({"a": 1})
    with pytest.raises(ValueError):
        hash_arguments({"a": float("nan")})


async def test_audit_failure_leaves_consumption_committed(
    mcp_scope: Scope,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    id = await mcp_scope.seed()
    monkeypatch.setattr(mcp_scope.service._audit, "log_event", AsyncMock(side_effect=OSError))
    with pytest.raises(OSError):
        await mcp_scope.invoke(id)
    assert await mcp_scope.status(id) == "CONSUMED"
    mcp_scope.call.assert_not_awaited()


async def test_mcp_integration_runs_offline_with_mock_subprocess(
    mcp_scope: Scope, monkeypatch: pytest.MonkeyPatch
) -> None:
    process = FakeServer()
    spawn = AsyncMock(return_value=process)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    client = MCPClient([MCPServerConfig(name="server", command=["configured"])])
    service = MCPService(client, AuditLogRepository(mcp_scope.session), mcp_scope.repository)
    approval_id = await mcp_scope.seed()
    result = await service.invoke_tool("server", "write", ARGS, "actor", approval_id)
    assert process.arguments == ARGS and result.content[0]["text"] == "result"
    assert process.terminated and await mcp_scope.status(approval_id) == "CONSUMED"
    assert [name for name, _ in await mcp_scope.events()] == [
        "mcp_approval_granted",
        "mcp_tool_invoked",
        "mcp_tool_completed",
    ]
