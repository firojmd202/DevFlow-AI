"""Offline integration tests for Wave 2 specification approval and HTTP entry points."""

import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from streamlit.testing.v1 import AppTest

from devflow_api.executors.registry import ExecutorRegistry
from devflow_api.executors.specification import SpecGeneratorExecutor, SpecReviewerExecutor
from devflow_api.models import ApprovalRequest, WorkflowStepRun
from devflow_api.models.specification import SpecificationArtifact
from devflow_api.orchestration import WorkflowOrchestrator
from devflow_api.repositories._workflow_transaction import immediate_transaction
from devflow_api.repositories.specification_version import SpecificationVersionRepository
from devflow_api.repositories.workflow import WorkflowRepository
from devflow_api.schemas.ai_provider import ProviderResponse
from devflow_api.schemas.specification import AI_REVIEW_DISCLAIMER
from devflow_api.schemas.workflow_template import ToolSelection
from devflow_api.services.specification_approval import SpecificationApprovalService
from devflow_api.services.specification_review import SpecificationReviewService
from devflow_api.specification_errors import SpecDigestMismatchError
from devflow_core.config import Settings
from devflow_core.exceptions import ApprovalAlreadyResolvedError, ApprovalNotConsumableError
from devflow_ui.api_client import APIClient
from tests.conftest import ROOT
from tests.unit.test_wave2_specification_services import (
    ARTIFACTS,
    create_draft,
    generation_response,
    stub,
)
from tests.unit.test_wave2_specification_services import sessions as file_sessions  # noqa: F401

PREFIX = "/api/v1/specification-requests"


def review_response() -> ProviderResponse:
    return ProviderResponse(content='{"findings":[]}', model="mock-model", provider_id="ollama")


async def test_full_specification_lifecycle(
    api_app: FastAPI,
    test_client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    provider = stub(generation_response())
    provider.generate.side_effect = [generation_response(), review_response()]
    api_app.state.ai_provider = provider
    api_app.state.workflow_sessions = session_factory
    invalid = await test_client.post(PREFIX, json={"title": "test", "actor_id": "override"})
    assert invalid.status_code == 422
    created = await test_client.post(
        PREFIX, json={"title": "Feature", "description": "Store drafts."}
    )
    assert created.status_code == 201
    path = f"{PREFIX}/{created.json()['id']}"
    assert (await test_client.get(PREFIX + "/999")).status_code == 404
    generation = await test_client.post(path + "/generate")
    assert generation.status_code == 202
    assert (await test_client.get(generation.json()["poll_url"])).json()["status"] == "succeeded"
    history = (await test_client.get(path + "/versions")).json()
    version = history[0]
    binding = {"version_id": version["id"], "content_digest": version["content_digest"]}
    for kind, expected in ARTIFACTS.items():
        response = await test_client.get(f"{path}/versions/{version['id']}/artifacts/{kind}")
        assert response.json()["content"] == expected
    assert (await test_client.post(path + "/approval", json=binding)).status_code == 409
    review = await test_client.post(path + "/review")
    assert review.status_code == 202
    assert (await test_client.get(review.json()["poll_url"])).json()["status"] == "succeeded"
    assert (await test_client.get(path + "/review/findings")).json()[
        "disclaimer"
    ] == AI_REVIEW_DISCLAIMER
    pending = await test_client.post(path + "/approval", json=binding)
    assert pending.status_code == 200
    decision = {**binding, "approval_id": pending.json()["id"], "decision": "approved"}
    assert (await test_client.post(path + "/approve", json=decision)).status_code == 200
    assert (await test_client.get(path)).json()["status"] == "approved"
    assert (await test_client.post(path + "/approve", json=decision)).status_code == 409
    assert (await test_client.delete(path + "/generate")).status_code == 409
    assert (await test_client.delete(path)).status_code == 409
    audit = (await test_client.get(path + "/audit")).json()
    assert {"spec_approved", "spec_review_completed"} <= {event["event_type"] for event in audit}
    async with session_factory() as session:
        assert await session.scalar(select(ApprovalRequest.id)) is None
        assert await SpecificationApprovalService(session).is_implementation_authorized(
            created.json()["id"]
        )


async def ready(
    sessions: async_sessionmaker[AsyncSession],
    **fields: object,
) -> tuple[int, int, str]:
    request_id, version_id = await create_draft(sessions, **fields)
    async with sessions() as session, immediate_transaction(session):
        repo = SpecificationVersionRepository(session)
        for kind, content in ARTIFACTS.items():
            await repo.save_artifact(version_id, kind, content, commit=False)
        digest = await repo.compute_and_set_digest(version_id, commit=False)
        await repo.transition_status(version_id, "draft", "generated", commit=False)
    review = SpecificationReviewService(sessions, stub(review_response()))
    attempt = await review.start(version_id)
    assert (await review.run(attempt.id)).status == "succeeded"
    return request_id, version_id, digest


async def test_standalone_digest_failure_rolls_back_consume(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    req, ver, digest = await ready(session_factory)
    async with session_factory() as session:
        service = SpecificationApprovalService(session)
        actor = service.settings.LOCAL_OPERATOR_ID
        pending = await service.request_approval(req, actor, expected_version_id=ver)
        approval_id = pending.id
        async with immediate_transaction(session):
            await session.execute(
                update(SpecificationArtifact)
                .where(
                    SpecificationArtifact.specification_version_id == ver,
                    SpecificationArtifact.artifact_type == "design",
                )
                .values(content="tampered")
            )
        with pytest.raises(SpecDigestMismatchError):
            await service.resolve_standalone(
                approval_id,
                "approved",
                actor,
                request_id=req,
                expected_version_id=ver,
                expected_digest=digest,
            )
        assert (await service.standalone.get(approval_id)).consumed_at is None
        assert not await service.is_implementation_authorized(req)


@pytest.mark.parametrize("tampered", [False, True])
async def test_bound_approval_preserves_independent_dispatch_gate(
    session_factory: async_sessionmaker[AsyncSession],
    tampered: bool,
) -> None:
    config = Settings()
    async with session_factory() as session:
        workflow = await WorkflowRepository(session).create(
            {
                "name": "Workflow",
                "definition_json": json.dumps(
                    {
                        "template_version": 1,
                        "steps": [
                            {
                                "key": "spec",
                                "title": "Approve spec",
                                "version": 1,
                                "executor_id": "mock",
                                "tool_selection": {"executor_id": "mock"},
                                "inputs": {"value": "spec"},
                                "approvable": True,
                                "protected_operation": "specification_approval",
                            },
                            {
                                "key": "implementation",
                                "title": "Authorize implementation",
                                "version": 1,
                                "executor_id": "mock",
                                "tool_selection": {"executor_id": "mock"},
                                "approvable": True,
                                "protected_operation": "implementation_authorization",
                                "depends_on": ["spec"],
                            },
                        ],
                    }
                ),
            }
        )
        orchestrator = WorkflowOrchestrator(session, settings=config)
        run = await orchestrator.create_run(workflow.id)
        await orchestrator.start_or_resume(run.id)
        step = await session.scalar(
            select(WorkflowStepRun).where(
                WorkflowStepRun.workflow_run_id == run.id,
                WorkflowStepRun.step_key == "spec",
            )
        )
        assert step is not None and step.status == "WAITING_APPROVAL"
        run_id, step_id = run.id, step.id
    req, ver, digest = await ready(
        session_factory, workflow_run_id=run_id, workflow_step_id=step_id
    )
    async with session_factory() as session:
        service = SpecificationApprovalService(session, config)
        actor = config.LOCAL_OPERATOR_ID
        approval = await service.request_approval(req, actor, expected_version_id=ver)
        assert isinstance(approval, ApprovalRequest)
        approval_id = approval.id
        if tampered:
            async with immediate_transaction(session):
                await session.execute(
                    update(SpecificationArtifact)
                    .where(
                        SpecificationArtifact.specification_version_id == ver,
                    )
                    .values(content="tampered")
                )
            with pytest.raises(SpecDigestMismatchError):
                await service.resolve_bound(
                    approval_id,
                    "approved",
                    actor,
                    request_id=req,
                    expected_version_id=ver,
                    expected_digest=digest,
                )
            assert not await service.is_implementation_authorized(req)
            from devflow_api.repositories.workflow_step_run import WorkflowStepRunRepository

            assert approval.parameters_hash is not None
            with pytest.raises(ApprovalNotConsumableError):
                await WorkflowStepRunRepository(session).dispatch_protected_txn(
                    step_id,
                    "worker",
                    approval_id=approval_id,
                    operation="specification_approval",
                    parameters_hash=approval.parameters_hash,
                    actor_id=actor,
                )
        else:
            approved = await service.resolve_bound(
                approval_id,
                "approved",
                actor,
                request_id=req,
                expected_version_id=ver,
                expected_digest=digest,
            )
            assert approved.status == "approved"
            assert await service.is_implementation_authorized(req)
            with pytest.raises(ApprovalAlreadyResolvedError):
                await service.resolve_bound(
                    approval_id,
                    "approved",
                    actor,
                    request_id=req,
                    expected_version_id=ver,
                    expected_digest=digest,
                )
        row = await session.get(ApprovalRequest, approval_id, populate_existing=True)
        assert row is not None and row.status == "approved" and row.consumed_at is None
        if not tampered:
            await WorkflowOrchestrator(session, settings=config).start_or_resume(run_id)
            implementation = await session.scalar(
                select(WorkflowStepRun).where(
                    WorkflowStepRun.workflow_run_id == run_id,
                    WorkflowStepRun.step_key == "implementation",
                )
            )
            assert implementation is not None and implementation.status == "WAITING_APPROVAL"


def test_specification_executor_registration() -> None:
    registry = ExecutorRegistry()
    for executor in (SpecGeneratorExecutor(), SpecReviewerExecutor()):
        registry.register(executor)
        assert (
            registry.select(executor.executor_id, ToolSelection(executor_id=executor.executor_id))
            is executor
        )
    assert registry.select("mock", ToolSelection(executor_id="mock")).identifier.id == "mock"


def test_feature_request_ui_submits_via_api(monkeypatch: pytest.MonkeyPatch) -> None:
    async def respond(
        path: str = "",
        *,
        method: str = "GET",
        payload: dict[str, object] | None = None,
        params: dict[str, str | int] | None = None,
    ) -> object:
        if path == "/providers":
            return [{"provider_id": "ollama", "model_id": "mock", "available": True}]
        assert method == "POST" and payload is not None
        assert payload["provider_id"] == "ollama" and payload["description"] == "Store drafts."
        return {"id": 1}

    mock = AsyncMock(side_effect=respond)
    monkeypatch.setattr(APIClient, "specifications", mock)
    at = AppTest.from_file(
        str(ROOT / "src/devflow_ui/app_pages/7_Spec_Request.py"),
        default_timeout=15,
    ).run()
    assert not at.exception
    at.text_input[0].set_value("Example")
    at.text_area[0].set_value("Store drafts.")
    at.button[0].click().run()
    assert not at.exception and at.success


def test_openapi_export_parity(api_app: FastAPI) -> None:
    path: Path = ROOT / "docs/openapi.json"
    assert json.loads(path.read_text(encoding="utf-8")) == api_app.openapi()


async def test_streamlit_and_fastapi_share_the_specification_lifecycle(
    api_app: FastAPI,
    test_client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio
    from datetime import UTC, datetime

    from devflow_api.schemas.ai_provider import AvailabilityResult

    provider = stub(generation_response())
    provider.generate.side_effect = [generation_response(), review_response()]
    provider.check_availability.return_value = AvailabilityResult(
        available=True,
        provider_id="ollama",
        checked_at=datetime.now(UTC),
    )
    api_app.state.ai_provider = provider
    api_app.state.workflow_sessions = session_factory

    async def bridge(
        path: str = "",
        *,
        method: str = "GET",
        payload: dict[str, object] | None = None,
        params: dict[str, str | int] | None = None,
    ) -> object:
        response = await test_client.request(method, PREFIX + path, json=payload, params=params)
        assert response.status_code < 400, response.text
        return response.json()

    monkeypatch.setattr(APIClient, "specifications", AsyncMock(side_effect=bridge))

    def run_ui() -> None:
        pages = ROOT / "src/devflow_ui/app_pages"
        request = AppTest.from_file(str(pages / "7_Spec_Request.py"), default_timeout=15).run()
        request.text_input[0].set_value("Example")
        request.text_area[0].set_value("Store drafts.")
        request.button[0].click().run()
        assert not request.exception and request.success

        generation = AppTest.from_file(
            str(pages / "8_Generation_Status.py"),
            default_timeout=15,
        ).run()
        next(
            button for button in generation.button if button.label == "Generate specification"
        ).click().run()
        assert not generation.exception and generation.code

        review = AppTest.from_file(str(pages / "9_Review_Findings.py"), default_timeout=15).run()
        next(
            button for button in review.button if button.label == "Request AI review"
        ).click().run()
        assert not review.exception and any(
            AI_REVIEW_DISCLAIMER in info.value for info in review.info
        )

        approval = AppTest.from_file(str(pages / "10_Approval.py"), default_timeout=15).run()
        assert next(button for button in approval.button if button.label == "Approve").disabled
        next(
            button for button in approval.button if button.label == "Request approval"
        ).click().run()
        approval.checkbox[0].check().run()
        next(button for button in approval.button if button.label == "Approve").click().run()
        assert not approval.exception and any(
            "Approved specification" in msg.value for msg in approval.success
        )

    await asyncio.to_thread(run_ui)


@pytest.mark.parametrize(
    "content, expected_state, expected_error",
    [
        (
            '{"findings":[{"severity":"Critical","dimension":"security_privacy",'
            '"finding_text":"Unverified policy","location":"design.md",'
            '"recommendation":"Review"}]}',
            "revision_required",
            None,
        ),
        ('{"findings":[{"severity":"High"}]}', "ready_for_approval", "AI_REVIEW_MALFORMED"),
    ],
)
async def test_review_findings_cannot_bypass_approval(
    api_app: FastAPI,
    test_client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    content: str,
    expected_state: str,
    expected_error: str | None,
) -> None:
    provider = stub(ProviderResponse(content=content, model="mock", provider_id="ollama"))
    api_app.state.ai_provider = provider
    api_app.state.workflow_sessions = session_factory
    from tests.unit.test_wave2_specification_services import seed_generated

    rid, vid = await seed_generated(session_factory)
    path = f"{PREFIX}/{rid}"
    assert (await test_client.post(path + "/review")).status_code == 202
    assert (await test_client.get(path)).json()["status"] == expected_state
    review_status = (await test_client.get(path + "/status", params={"kind": "review"})).json()
    assert review_status["error_code"] == expected_error
    if expected_error is not None:
        assert review_status["status"] == "failed"
    versions = (await test_client.get(path + "/versions")).json()
    response = await test_client.post(
        path + "/approval",
        json={
            "version_id": vid,
            "content_digest": versions[0]["content_digest"],
        },
    )
    assert response.status_code == 409


async def test_executor_dispatch_generates_and_reviews(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_id, version_id = await create_draft(session_factory)
    provider = stub(generation_response())
    provider.generate.side_effect = [generation_response(), review_response()]
    monkeypatch.setattr(
        "devflow_api.services.specification_execution.ProviderFactory.create",
        lambda _: provider,
    )
    async with session_factory() as session:
        workflow = await WorkflowRepository(session).create(
            {
                "name": "Specification workflow",
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
                                "inputs": {"spec_request_id": request_id},
                            },
                            {
                                "key": "review",
                                "title": "Review",
                                "version": 1,
                                "executor_id": "spec_reviewer",
                                "tool_selection": {"executor_id": "spec_reviewer"},
                                "depends_on": ["generate"],
                                "inputs": {"spec_version_id": version_id},
                            },
                        ],
                    }
                ),
            }
        )
        orchestrator = WorkflowOrchestrator(session)
        run = await orchestrator.create_run(workflow.id)
        completed = await orchestrator.start_or_resume(run.id)
        assert completed.status == "completed"
        steps = list(
            await session.scalars(
                select(WorkflowStepRun).where(WorkflowStepRun.workflow_run_id == run.id)
            )
        )
        assert {item.status for item in steps} == {"SUCCEEDED"}
        assert any(
            item.artifact_refs_json and "requirements.md" in item.artifact_refs_json
            for item in steps
        )
        assert (
            await SpecificationVersionRepository(session).get_version(version_id)
        ).status == "ready_for_approval"
        assert provider.generate.await_count == 2
        replayed = await orchestrator.create_run(workflow.id)
        assert (await orchestrator.start_or_resume(replayed.id)).status == "completed"
        assert provider.generate.await_count == 2


async def test_simultaneous_standalone_resolution_has_one_winner(
    file_sessions: async_sessionmaker[AsyncSession],  # noqa: F811
) -> None:
    import asyncio

    request_id, version_id, digest = await ready(file_sessions)
    async with file_sessions() as session:
        service = SpecificationApprovalService(session)
        actor = service.settings.LOCAL_OPERATOR_ID
        approval = await service.request_approval(request_id, actor, expected_version_id=version_id)
        approval_id = approval.id

    async def resolve() -> str:
        async with file_sessions() as session:
            service = SpecificationApprovalService(session)
            try:
                return (
                    await service.resolve_standalone(
                        approval_id,
                        "approved",
                        actor,
                        request_id=request_id,
                        expected_version_id=version_id,
                        expected_digest=digest,
                    )
                ).status
            except ApprovalAlreadyResolvedError:
                return "replay_rejected"

    assert set(await asyncio.gather(resolve(), resolve())) == {"approved", "replay_rejected"}


async def test_approval_binding_expiration_and_rejection(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from datetime import UTC, datetime, timedelta

    from devflow_api.models.specification import SpecificationApprovalRequest
    from devflow_api.specification_errors import ApprovalBindingMismatch
    from devflow_core.exceptions import ApprovalExpiredError

    rid, vid, digest = await ready(session_factory)
    async with session_factory() as session:
        service = SpecificationApprovalService(session)
        actor = service.settings.LOCAL_OPERATOR_ID
        with pytest.raises(ApprovalBindingMismatch):
            await service.request_approval(rid, "different-operator", expected_version_id=vid)
        with pytest.raises(ApprovalBindingMismatch):
            await service.request_approval(rid, actor, expected_version_id=vid + 1)
        approval = await service.request_approval(rid, actor, expected_version_id=vid)
        assert isinstance(approval, SpecificationApprovalRequest)
        approval_id = approval.id
        assert (
            await service.request_approval(rid, actor, expected_version_id=vid)
        ).id == approval_id
        async with immediate_transaction(session):
            approval.operation = "unexpected"
        with pytest.raises(ApprovalBindingMismatch):
            await service.resolve_standalone(
                approval_id,
                "approved",
                actor,
                request_id=rid,
                expected_version_id=vid,
                expected_digest=digest,
            )
        approved_row = await service.standalone.get(approval_id)
        async with immediate_transaction(session):
            approved_row.operation = "approve_specification"
            approved_row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        with pytest.raises(ApprovalExpiredError):
            await service.resolve_standalone(
                approval_id,
                "approved",
                actor,
                request_id=rid,
                expected_version_id=vid,
                expected_digest=digest,
            )
        valid = await service.request_approval(rid, actor, expected_version_id=vid)
        assert valid.id != approval_id
        result = await service.resolve_standalone(
            valid.id,
            "rejected",
            actor,
            request_id=rid,
            expected_version_id=vid,
            expected_digest=digest,
        )
        assert result.status == "revision_required"


@pytest.mark.parametrize("mode", ["pending", "running", "failed", "cancelled", "empty", "offline"])
def test_generation_ui_states(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    async def respond(
        path: str = "",
        *,
        method: str = "GET",
        payload: dict[str, object] | None = None,
        params: dict[str, str | int] | None = None,
    ) -> object:
        if not path:
            if mode == "offline":
                return None
            if mode == "empty":
                return []
            return [{"id": 7, "title": "Example", "status": "generating", "version": 1}]
        if path.endswith("/status"):
            return {"status": mode, "error_code": "PROVIDER_UNAVAILABLE"}
        if method == "DELETE":
            return {"status": "cancellation_requested"}
        return []

    monkeypatch.setattr(APIClient, "specifications", AsyncMock(side_effect=respond))
    at = AppTest.from_file(
        str(ROOT / "src/devflow_ui/app_pages/8_Generation_Status.py"),
        default_timeout=15,
    ).run()
    assert not at.exception
    if mode in {"failed", "offline"}:
        assert at.error
    else:
        assert at.info
    if mode in {"pending", "running"}:
        assert next(
            button for button in at.button if button.label == "Generate specification"
        ).disabled
        next(button for button in at.button if button.label == "Cancel generation").click().run()
        assert not at.exception and at.success


@pytest.mark.parametrize("failure", ["APPROVAL_EXPIRED", "SPEC_DIGEST_MISMATCH"])
def test_approval_ui_reports_stale_or_expired_decisions(
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    async def respond(
        self: APIClient,
        path: str = "",
        *,
        method: str = "GET",
        payload: dict[str, object] | None = None,
        params: dict[str, str | int] | None = None,
    ) -> object:
        if not path:
            return [{"id": 7, "title": "Example", "version": 1, "status": "ready_for_approval"}]
        if path.endswith("/versions"):
            return [{"id": 1, "version_number": 1, "content_digest": "a" * 64}]
        if path.endswith("/status"):
            return {"status": "succeeded"}
        if path.endswith("/findings"):
            return {"findings": []}
        if path.endswith("/approval"):
            return {"id": 1, "status": "pending"}
        if path.endswith("/approve"):
            self.last_error_code = failure
            return None
        return []

    monkeypatch.setattr(APIClient, "specifications", respond)
    at = AppTest.from_file(
        str(ROOT / "src/devflow_ui/app_pages/10_Approval.py"),
        default_timeout=15,
    ).run()
    next(button for button in at.button if button.label == "Request approval").click().run()
    at.checkbox[0].check().run()
    next(button for button in at.button if button.label == "Approve").click().run()
    assert not at.exception and at.error
    message = "expired" if failure == "APPROVAL_EXPIRED" else "digest changed"
    assert message in at.error[0].value


async def test_review_acknowledgment_expired_approval_and_revision_api(
    api_app: FastAPI,
    test_client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from datetime import UTC, datetime, timedelta

    from devflow_api.models.specification import SpecificationApprovalRequest
    from tests.unit.test_wave2_specification_services import seed_generated

    rid, vid = await seed_generated(session_factory)
    api_app.state.ai_provider = stub(
        ProviderResponse(
            content=json.dumps(
                {
                    "findings": [
                        {
                            "severity": "High",
                            "dimension": "testability",
                            "finding_text": "Insufficient examples",
                            "location": "requirements.md",
                            "recommendation": "Add examples",
                        }
                    ]
                }
            ),
            model="mock",
            provider_id="ollama",
        )
    )
    api_app.state.workflow_sessions = session_factory
    path = f"{PREFIX}/{rid}"
    assert (await test_client.post(path + "/review")).status_code == 202
    findings = (await test_client.get(path + "/review/findings")).json()
    fid = findings["findings"][0]["id"]
    digest = (await test_client.get(path + "/versions")).json()[0]["content_digest"]
    body = {"version_id": vid, "content_digest": digest}
    assert (await test_client.post(path + "/approval", json=body)).status_code == 409
    assert (await test_client.post(path + f"/findings/{fid}/acknowledge")).json()["acknowledged"]
    request = await test_client.post(path + "/approval", json=body)
    assert request.status_code == 200
    aid = request.json()["id"]
    async with session_factory() as session, immediate_transaction(session):
        approval = await session.get(SpecificationApprovalRequest, aid)
        assert approval is not None
        approval.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    expired = await test_client.post(
        path + "/approve",
        json={
            **body,
            "approval_id": aid,
            "decision": "approved",
        },
    )
    assert expired.status_code == 409 and expired.json()["code"] == "APPROVAL_EXPIRED"
    retry = await test_client.post(path + "/approval", json=body)
    assert retry.status_code == 200 and retry.json()["id"] != aid
    rejected = await test_client.post(
        path + "/approve",
        json={
            **body,
            "approval_id": retry.json()["id"],
            "decision": "rejected",
            "reason": "Clarify.",
        },
    )
    assert rejected.status_code == 200 and rejected.json()["status"] == "rejected"
    draft = await test_client.patch(
        path,
        json={
            "title": "Revision",
            "description": "Add examples.",
            "expected_version": 1,
        },
    )
    assert draft.status_code == 200 and draft.json()["version"] == 2
    history = await test_client.get(path + "/review/findings", params={"version_id": vid})
    assert history.json()["summary"] == {"High": 1}
    audit = (await test_client.get(path + "/audit")).json()
    assert {"spec_approval_expired", "spec_approval_rejected"} <= {
        item["event_type"] for item in audit
    }
    assert (await test_client.delete(path)).status_code == 204
    assert (await test_client.get(path)).json()["status"] == "cancelled"


async def test_generation_provider_failure_and_cancellation_api(
    api_app: FastAPI,
    test_client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from devflow_api.providers.exceptions import ProviderUnavailableError
    from devflow_api.services.specification_generation import SpecificationGenerationService

    rid, _ = await create_draft(session_factory)
    provider = stub(generation_response())
    provider.generate.side_effect = [
        ProviderUnavailableError("ollama", "mock"),
        generation_response(),
    ]
    api_app.state.ai_provider = provider
    api_app.state.workflow_sessions = session_factory
    path = f"{PREFIX}/{rid}"
    assert (await test_client.get(PREFIX, params={"limit": 1})).json()[0]["id"] == rid
    assert (
        await test_client.post(path + "/generate", json={"provider_id": "openai"})
    ).status_code == 400
    first = await test_client.post(path + "/generate")
    assert first.status_code == 202
    assert (await test_client.get(first.json()["poll_url"])).json()[
        "error_code"
    ] == "PROVIDER_UNAVAILABLE"
    worker = SpecificationGenerationService(session_factory, provider)
    pending = await worker.start(rid, expected_version=1)
    cancelled = await test_client.delete(path + "/generate")
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancellation_requested"
    assert (await worker.run(pending.id)).status == "cancelled"
    assert (await test_client.post(path + "/generate")).status_code == 202
    assert (await test_client.get(path)).json()["status"] == "generated"


@pytest.mark.parametrize("mode", ["compare", "missing", "progress_missing", "generate_error"])
def test_artifact_comparison_and_generation_errors(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    async def respond(
        self: APIClient,
        path: str = "",
        *,
        method: str = "GET",
        payload: dict[str, object] | None = None,
        params: dict[str, str | int] | None = None,
    ) -> object:
        if not path:
            lifecycle = "draft" if mode == "generate_error" else "generated"
            return [{"id": 7, "title": "Feature", "status": lifecycle, "version": 2}]
        if path.endswith("/status"):
            return None if mode == "progress_missing" else {"status": "succeeded"}
        if path.endswith("/versions"):
            return [
                {"id": 1, "version_number": 1, "content_digest": "a" * 64},
                {"id": 2, "version_number": 2, "content_digest": "b" * 64},
            ]
        if path.endswith("/generate"):
            self.last_error_code = "PROVIDER_UNAVAILABLE"
            return None
        return None if mode == "missing" else {"content": "Artifact body"}

    monkeypatch.setattr(APIClient, "specifications", respond)
    at = AppTest.from_file(
        str(ROOT / "src/devflow_ui/app_pages/8_Generation_Status.py"),
        default_timeout=15,
    ).run()
    if mode == "compare":
        at.selectbox[2].select("1").run()
        assert len(at.code) == 2
    elif mode == "generate_error":
        next(
            button for button in at.button if button.label == "Generate specification"
        ).click().run()
        assert "PROVIDER_UNAVAILABLE" in at.error[0].value
    else:
        assert at.error
    assert not at.exception


@pytest.mark.parametrize("mode", ["pending", "cancel_error", "failed", "critical", "revision"])
def test_review_ui_cancellation_and_revision(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    saved = False
    acknowledged = False

    async def respond(
        path: str = "",
        *,
        method: str = "GET",
        payload: dict[str, object] | None = None,
        params: dict[str, str | int] | None = None,
    ) -> object:
        nonlocal saved, acknowledged
        if not path:
            lifecycle = (
                "under_review" if mode in {"pending", "cancel_error"} else "revision_required"
            )
            return [
                {
                    "id": 7,
                    "title": "Feature",
                    "status": "draft" if saved else lifecycle,
                    "description": "Original",
                    "version": 1,
                    "acceptance_criteria": ["Works"],
                }
            ]
        if path.endswith("/status"):
            state = "running" if mode in {"pending", "cancel_error"} else mode
            return {"status": state, "error_code": "AI_REVIEW_MALFORMED"}
        if path.endswith("/versions"):
            return [{"id": 1, "version_number": 1}]
        if path.endswith("/findings"):
            return {
                "disclaimer": AI_REVIEW_DISCLAIMER,
                "findings": [
                    {
                        "id": 3,
                        "severity": "Critical",
                        "location": "design.md",
                        "finding_text": "Missing security",
                        "recommendation": "Fix",
                        "acknowledged": acknowledged,
                    }
                ],
            }
        if path.endswith("/acknowledge"):
            acknowledged = True
            return {"acknowledged": True}
        if method == "PATCH":
            saved = True
            assert payload is not None and payload["acceptance_criteria"] == ["Works"]
            return {"id": 7}
        if method == "DELETE":
            return None if mode == "cancel_error" else {"status": "cancellation_requested"}
        raise AssertionError(path)

    monkeypatch.setattr(APIClient, "specifications", AsyncMock(side_effect=respond))
    at = AppTest.from_file(
        str(ROOT / "src/devflow_ui/app_pages/9_Review_Findings.py"),
        default_timeout=15,
    ).run()
    assert not at.exception
    if mode in {"pending", "cancel_error"}:
        next(button for button in at.button if button.label == "Cancel review").click().run()
        assert at.error if mode == "cancel_error" else at.success
    elif mode == "critical":
        next(button for button in at.button if button.label == "Acknowledge").click().run()
        assert acknowledged and not at.exception
    elif mode == "revision":
        next(button for button in at.button if button.label == "Save revised draft").click().run()
        assert saved and not at.exception
    else:
        assert any("AI_REVIEW_MALFORMED" in item.value for item in at.error)


async def test_review_cancel_and_resource_checks(
    api_app: FastAPI,
    test_client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from tests.unit.test_wave2_specification_services import seed_generated

    request_id, version_id = await seed_generated(session_factory)
    other_id, _ = await create_draft(session_factory)
    prefix = f"{PREFIX}/{request_id}"
    api_app.state.workflow_sessions = session_factory
    provider = stub(review_response())
    api_app.state.ai_provider = provider
    service = SpecificationReviewService(session_factory, provider)
    pending = await service.start(version_id)
    assert (await test_client.delete(prefix + "/review")).status_code == 200
    assert (await service.run(pending.id)).status == "cancelled"
    assert (await test_client.delete(prefix + "/review")).status_code == 409
    assert (await test_client.delete(f"{PREFIX}/{other_id}/review")).status_code == 409
    assert (
        await test_client.get(f"{PREFIX}/{other_id}/versions/{version_id}/artifacts/design")
    ).status_code == 404
    assert (
        await test_client.post(prefix + "/review", json={"expected_version": 5})
    ).status_code == 409
    current = await service.start(version_id)
    assert (await test_client.post(prefix + "/revision")).json()["status"] == "revision_required"
    assert (await service.get_attempt(current.id)).status == "cancelled"


@pytest.mark.parametrize("mode", ["cancelled", "handler_error", "domain_error", "missing_handler"])
async def test_specification_executor_normalizes_failure(mode: str) -> None:
    from devflow_api.schemas.executor import CancellationHandle, ExecutionContext
    from devflow_api.specification_errors import AttemptConflictError

    async def handle(context: ExecutionContext) -> dict[str, object]:
        if mode == "domain_error":
            raise AttemptConflictError("PROVIDER_UNAVAILABLE")
        raise OSError("Private failure detail")

    executor = SpecGeneratorExecutor(None if mode == "missing_handler" else handle)
    context = ExecutionContext(
        run_id=1,
        step_run_id=2,
        step_key="generate",
        step_version=1,
        timeout_s=10,
        inputs={"spec_request_id": 1},
        tool_selection=ToolSelection(executor_id="spec_generator"),
        cancellation=CancellationHandle(cancelled=mode == "cancelled"),
        actor_id="local_operator",
        idempotency_key="test",
        input_digest="a" * 64,
        attempt=1,
    )
    result = await executor.execute(context)
    assert result.error is not None and "Private" not in result.error.message
    assert result.outcome == ("cancelled" if mode == "cancelled" else "failed")
    if mode == "domain_error":
        assert result.error.code == "PROVIDER_UNAVAILABLE"


async def test_provider_listing_never_pings_the_configured_cloud_provider(
    api_app: FastAPI,
    test_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_secret: str,
) -> None:
    from pydantic import SecretStr

    cloud = stub(review_response())
    cloud.provider_id = "openai"
    local = stub(review_response())
    local.check_availability.side_effect = TimeoutError()
    api_app.state.ai_provider = cloud
    api_app.state.settings = Settings(
        AI_PROVIDER="openai", OPENAI_API_KEY=SecretStr(synthetic_secret)
    )
    monkeypatch.setattr(
        "devflow_api.routers.specification_requests.ProviderFactory.create", lambda _: local
    )
    response = await test_client.get(PREFIX + "/providers")
    assert response.status_code == 200
    assert [row["provider_id"] for row in response.json()] == ["ollama", "openai"]
    assert response.json()[0]["available"] is False
    assert response.json()[1]["available"] is None
    assert synthetic_secret not in response.text
    cloud.check_availability.assert_not_awaited()
