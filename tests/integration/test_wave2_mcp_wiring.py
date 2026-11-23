"""Offline FastAPI and workflow coverage of the Wave 2 MCP transport path."""

import asyncio
import json
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from devflow_api.models.specification import GenerationAttempt
from devflow_api.orchestration import WorkflowOrchestrator
from devflow_api.repositories.specification_version import SpecificationVersionRepository
from devflow_api.repositories.workflow import WorkflowRepository
from devflow_core.config import Settings
from devflow_core.mcp_arguments import hash_arguments
from tests.mcp_fakes import FakeServer
from tests.unit.test_wave2_specification_services import create_draft, generation_response, stub

PREFIX = "/api/v1/specification-requests"
ARGUMENTS = {"query": "private context request"}
PLAN = {"server": "local", "tool": "read", "arguments": ARGUMENTS, "required": True}
PRIVATE = "private protocol detail"


@pytest.fixture
def mcp_settings() -> Settings:
    return Settings(
        GITHUB_TOKEN=SecretStr(PRIVATE),
        MCP_STRICT_SCHEMA_VALIDATION=True,
        MCP_SERVERS_CONFIG=json.dumps(
            [
                {
                    "name": "local",
                    "command": ["fake-mcp"],
                    "allowed_tools": ["read", "write"],
                    "tool_classifications": {"read": "read_only", "write": "consequential"},
                    "tool_schemas": {
                        "read": {
                            "type": "object",
                            "required": ["query"],
                            "properties": {"query": {"type": "string"}},
                            "additionalProperties": False,
                        }
                    },
                }
            ]
        ),
    )


@pytest.mark.parametrize(
    ("case", "change", "audit_status", "outcome"),
    [
        ("success", {}, "success", "succeeded"),
        ("required", {}, "failed", "failed"),
        ("optional", {"required": False}, "failed", "succeeded"),
        ("unknown_server", {"server": "unknown"}, "denied", "failed"),
        ("unauthorized_tool", {"tool": "write"}, "denied", "failed"),
        ("wildcard", {"tool": "*"}, "denied", "failed"),
        ("arguments", {"arguments": {"query": 42}}, "invalid_arguments", "failed"),
        ("none", {}, None, "succeeded"),
    ],
)
async def test_mcp_context_through_http_generation(
    api_app: FastAPI,
    test_client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    mcp_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    change: dict[str, object],
    audit_status: str | None,
    outcome: str,
) -> None:
    api_app.state.settings = mcp_settings
    api_app.state.workflow_sessions = session_factory
    provider = stub(generation_response())
    api_app.state.ai_provider = provider
    process = FakeServer()
    process.tool_text = "MCP evidence " + PRIVATE + " context " * 6000
    if case in {"required", "optional"}:
        process.outcome = "error"
    spawn = AsyncMock(return_value=process)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)

    request_id, version_id = await create_draft(session_factory)
    path = f"{PREFIX}/{request_id}"
    contexts = [] if case == "none" else [{**PLAN, **change}]
    accepted = await test_client.post(path + "/generate", json={"mcp_contexts": contexts})
    assert accepted.status_code == 202, accepted.text
    polled = await test_client.get(accepted.json()["poll_url"])
    assert polled.status_code == 200 and polled.json()["status"] == outcome
    assert PRIVATE not in polled.text
    audit = await test_client.get(path + "/audit")
    assert audit.status_code == 200
    assert PRIVATE not in audit.text and ARGUMENTS["query"] not in audit.text
    events = [event for event in audit.json() if event["event_type"] == "mcp_tool_invoked"]

    if audit_status is None:
        assert events == []
    else:
        assert len(events) == 1
        payload = json.loads(events[0]["payload_json"])
        assert payload["result_status"] == audit_status
        assert payload["specification_request_id"] == request_id
        assert payload["generation_attempt_id"] == int(accepted.json()["task_id"])
        if case in {"success", "required", "optional"}:
            assert (payload["server_name"], payload["tool_name"]) == ("local", "read")
            assert payload["argument_hash"] == hash_arguments(dict(ARGUMENTS))
            spawn.assert_awaited_once()
            invocation = spawn.await_args
            assert invocation is not None and invocation.args[0] == "fake-mcp"
            assert process.arguments == ARGUMENTS and process.calls.count("tools/call") == 1
        else:
            spawn.assert_not_awaited()
            assert "tools/call" not in process.calls

    if case == "none":
        spawn.assert_not_awaited()
    async with session_factory() as session:
        repo = SpecificationVersionRepository(session)
        if outcome == "failed":
            assert polled.json()["error_code"] == "MCP_CONTEXT_FAILURE"
            assert await repo.artifact_contents(version_id) == {}
            assert (await repo.get_request(request_id)).status == "draft"
            provider.generate.assert_not_awaited()
        else:
            assert await repo.verify_digest(version_id)
            assert (await repo.get_request(request_id)).status == "generated"
            provider.generate.assert_awaited_once()
            prompt = provider.generate.call_args.args[0]
            assert len(prompt) <= mcp_settings.AI_MAX_PROMPT_TOKENS * 4
            assert PRIVATE not in prompt
            if case == "success":
                _, untrusted = prompt.split("--- BEGIN MCP CONTEXT (untrusted", 1)
                assert "MCP evidence" in untrusted
            else:
                assert "MCP evidence" not in prompt


async def test_mcp_context_through_registered_workflow_executor(
    session_factory: async_sessionmaker[AsyncSession],
    mcp_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sqlalchemy import select

    from devflow_api.models.audit import WorkflowAuditLog
    from devflow_api.models.workflow_step_run import WorkflowStepRun

    request_id, version_id = await create_draft(session_factory)
    process = FakeServer()
    process.tool_text = "Workflow MCP evidence"
    spawn = AsyncMock(return_value=process)
    provider = stub(generation_response())
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(
        "devflow_api.services.specification_execution.ProviderFactory.create", lambda _: provider
    )
    async with session_factory() as session:
        workflow = await WorkflowRepository(session).create(
            {
                "name": "MCP specification",
                "definition_json": json.dumps(
                    {
                        "template_version": 1,
                        "steps": [
                            {
                                "key": "generate",
                                "title": "Generate",
                                "version": 1,
                                "executor_id": "spec_generator",
                                "tool_selection": {"executor_id": "spec_generator"},
                                "inputs": {"spec_request_id": request_id, "mcp_contexts": [PLAN]},
                            },
                            {
                                "key": "implement",
                                "title": "Implementation gate",
                                "version": 1,
                                "executor_id": "mock",
                                "tool_selection": {"executor_id": "mock"},
                                "depends_on": ["generate"],
                                "approvable": True,
                                "protected_operation": "implementation_authorization",
                            },
                        ],
                    }
                ),
            }
        )
        orchestrator = WorkflowOrchestrator(session, settings=mcp_settings)
        run = await orchestrator.create_run(workflow.id)
        assert (await orchestrator.start_or_resume(run.id)).status == "waiting_approval"
        assert (await orchestrator.start_or_resume(run.id)).status == "waiting_approval"
        step = await session.scalar(
            select(WorkflowStepRun).where(
                WorkflowStepRun.workflow_run_id == run.id,
                WorkflowStepRun.step_key == "implement",
            )
        )
        assert step is not None and step.status == "WAITING_APPROVAL" and step.attempt == 0
        attempt = await session.scalar(
            select(GenerationAttempt).where(
                GenerationAttempt.specification_request_id == request_id,
            )
        )
        assert attempt is not None and attempt.status == "succeeded"
        assert attempt.specification_version_id == version_id
        audit = await session.scalar(
            select(WorkflowAuditLog).where(
                WorkflowAuditLog.workflow_run_id == run.id,
                WorkflowAuditLog.event_type == "mcp_tool_invoked",
            )
        )
        assert audit is not None and audit.payload_json is not None
        payload = json.loads(audit.payload_json)
        assert payload["generation_attempt_id"] == attempt.id
        assert payload["specification_request_id"] == request_id
    assert process.arguments == ARGUMENTS and process.calls.count("tools/call") == 1
    spawn.assert_awaited_once()
    provider.generate.assert_awaited_once()
    assert "Workflow MCP evidence" in provider.generate.call_args.args[0]


async def test_duplicate_http_generation_cannot_launch_another_context_tool(
    api_app: FastAPI,
    test_client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    mcp_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api_app.state.settings = mcp_settings
    api_app.state.workflow_sessions = session_factory
    provider = stub(generation_response())
    api_app.state.ai_provider = provider
    process = FakeServer()
    launched, resume = asyncio.Event(), asyncio.Event()

    async def delayed_spawn(*args: object, **kwargs: object) -> FakeServer:
        launched.set()
        await resume.wait()
        return process

    spawn = AsyncMock(side_effect=delayed_spawn)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    request_id, _ = await create_draft(session_factory)
    async with asyncio.timeout(10), asyncio.TaskGroup() as tasks:
        path = f"{PREFIX}/{request_id}/generate"
        accepted = tasks.create_task(test_client.post(path, json={"mcp_contexts": [PLAN]}))
        try:
            await launched.wait()
            duplicate = await test_client.post(path, json={"mcp_contexts": [PLAN]})
            assert duplicate.status_code == 409
            assert duplicate.json()["code"] == "GENERATION_ALREADY_IN_PROGRESS"
        finally:
            resume.set()
    assert accepted.result().status_code == 202
    spawn.assert_awaited_once()
    provider.generate.assert_awaited_once()
