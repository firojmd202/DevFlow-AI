import ast
import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from devflow_api.main import create_app
from devflow_api.models.audit import WorkflowAuditLog
from devflow_api.models.specification import (
    GenerationAttempt,
    ReviewAttempt,
    SpecificationApprovalRequest,
)
from devflow_api.repositories._workflow_transaction import immediate_transaction
from devflow_api.repositories.approval import AuditLogRepository
from devflow_api.repositories.specification_approval import SpecificationApprovalRepository
from devflow_api.repositories.specification_version import SpecificationVersionRepository
from devflow_api.services.specification_generation import SpecificationGenerationService
from devflow_api.services.specification_recovery import SpecificationRecoveryService
from devflow_api.services.specification_review import SpecificationReviewService
from devflow_api.specification_errors import ApprovalBindingMismatch
from devflow_core.config import Settings
from devflow_core.exceptions import ApprovalAlreadyResolvedError
from tests.unit.test_wave2_specification_services import (
    ARTIFACTS,
    create_draft,
    generation_response,
    seed_generated,
    sessions,  # noqa: F401
    stub,
)


async def test_wave2_startup_recovers_without_replaying_attempts(
    sessions: async_sessionmaker[AsyncSession],  # noqa: F811
) -> None:
    provider = stub(generation_response())
    draft_id, draft_version_id = await create_draft(sessions)
    second_draft_id, _ = await create_draft(sessions)
    review_request_id, review_version_id = await seed_generated(sessions)
    generation = SpecificationGenerationService(sessions, provider)
    review = SpecificationReviewService(sessions, provider)
    pending = await generation.start(draft_id, expected_version=1)
    running_generation = await generation.start(second_draft_id, expected_version=1)
    running = await review.start(review_version_id)
    now = datetime.now(UTC)
    async with sessions() as session, immediate_transaction(session):
        generation_row = await session.get(GenerationAttempt, running_generation.id)
        assert generation_row is not None
        generation_row.status = "running"
        row = await session.get(ReviewAttempt, running.id)
        assert row is not None
        row.status = "running"
        row.cancellation_requested = 1
        for expiry, consumed, rejected in (
            (now - timedelta(minutes=1), None, None),
            (now + timedelta(minutes=1), None, None),
            (now - timedelta(minutes=1), now, None),
            (now - timedelta(minutes=1), None, now),
        ):
            session.add(
                SpecificationApprovalRequest(
                    specification_version_id=review_version_id,
                    parameters_hash="digest",
                    actor_id="operator",
                    expires_at=expiry,
                    consumed_at=consumed,
                    rejected_at=rejected,
                )
            )
        assert isinstance(session.bind, AsyncEngine)
        url = str(session.bind.url)

    app = create_app(Settings(DATABASE_URL=url))
    async with app.router.lifespan_context(app):
        assert app.state.recovered_specifications == {
            "generations": 2,
            "reviews": 1,
            "expired_approvals": 1,
        }
    async with sessions() as session:
        assert await SpecificationRecoveryService(session).recover() == {
            "generations": 0,
            "reviews": 0,
            "expired_approvals": 0,
        }
        repo = SpecificationVersionRepository(session)
        assert (await repo.get_request(draft_id)).status == "draft"
        assert (await repo.get_request(second_draft_id)).status == "draft"
        assert (await repo.get_version(draft_version_id)).status == "draft"
        assert (await repo.get_request(review_request_id)).status == "generated"
        assert (await repo.get_version(review_version_id)).status == "generated"
        assert await repo.verify_digest(review_version_id)
        for attempt in (
            await session.get(GenerationAttempt, pending.id),
            await session.get(GenerationAttempt, running_generation.id),
            await session.get(ReviewAttempt, running.id),
        ):
            assert attempt is not None
            assert (attempt.status, attempt.error_code) == ("failed", "INTERRUPTED")
            assert attempt.completed_at is not None
        events = list(
            await session.scalars(
                select(WorkflowAuditLog)
                .where(
                    WorkflowAuditLog.event_type.in_(
                        (
                            "spec_generation_failed",
                            "spec_review_failed",
                            "spec_approval_expired",
                        )
                    ),
                )
                .order_by(WorkflowAuditLog.id)
            )
        )
        assert [event.event_type for event in events] == [
            "spec_generation_failed",
            "spec_generation_failed",
            "spec_review_failed",
            "spec_approval_expired",
        ]
        assert all(event.workflow_run_id is None for event in events)
        approvals = list(
            await session.scalars(
                select(SpecificationApprovalRequest).order_by(
                    SpecificationApprovalRequest.id,
                )
            )
        )
        assert approvals[0].consumed_at is None and approvals[0].rejected_at is None
    assert (await generation.run(pending.id)).status == "failed"
    assert (await review.run(running.id)).status == "failed"
    provider.generate.assert_not_awaited()


def test_wave2_service_and_adapter_sources_have_no_execution_calls() -> None:
    api = Path(__file__).resolve().parents[2] / "src" / "devflow_api"
    paths = [
        *api.glob("services/specification*.py"),
        *api.glob("providers/*.py"),
        api / "adapters" / "mcp_adapter.py",
        api / "executors" / "specification.py",
    ]
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                assert all(alias.name != "subprocess" for alias in node.names), path
            elif isinstance(node, ast.ImportFrom):
                assert node.module != "subprocess", path
                if node.module == "os":
                    assert all(alias.name != "system" for alias in node.names), path
            elif isinstance(node, ast.Call):
                assert ast.unparse(node.func) not in {"exec", "eval", "os.system"}, path


async def test_wave2_generation_redacts_configured_cloud_key(
    sessions: async_sessionmaker[AsyncSession],  # noqa: F811
    synthetic_secret: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    request_id, version_id = await create_draft(sessions)
    output = ARTIFACTS.copy()
    output["requirements"] += "\n\n" + synthetic_secret
    provider = stub(generation_response(output))
    config = Settings(AI_PROVIDER="ollama", OPENAI_API_KEY=SecretStr(synthetic_secret))
    service = SpecificationGenerationService(sessions, provider, settings=config)
    attempt = await service.start(request_id, expected_version=1)
    assert (await service.run(attempt.id, actor_id=synthetic_secret)).status == "succeeded"
    captured = capsys.readouterr()
    assert synthetic_secret not in captured.out + captured.err
    async with sessions() as session:
        tables = (
            "specification_requests",
            "specification_versions",
            "specification_artifacts",
            "generation_attempts",
            "workflow_audit_log",
        )
        for table in tables:
            rows = await session.execute(text("SELECT * FROM " + table))  # noqa: S608
            assert synthetic_secret not in str(rows.all())
        contents = await SpecificationVersionRepository(session).artifact_contents(version_id)
        assert "[REDACTED]" in contents["requirements"]


async def test_wave2_standalone_consumption_requires_matching_hash_and_one_winner(
    sessions: async_sessionmaker[AsyncSession],  # noqa: F811
) -> None:
    _, version_id = await create_draft(sessions)
    async with sessions() as session:
        repo = SpecificationApprovalRepository(session)
        row = await repo.create(
            version_id, "original", "operator", datetime.now(UTC) + timedelta(minutes=1)
        )
        approval_id = row.id
        with pytest.raises(ApprovalBindingMismatch):
            await repo.consume_atomic(approval_id, version_id, "changed", "operator")
        assert (await repo.get(approval_id)).consumed_at is None

    async def consume() -> bool:
        async with sessions() as session:
            return await SpecificationApprovalRepository(session).consume_atomic(
                approval_id, version_id, "original", "operator"
            )

    results = await asyncio.gather(consume(), consume(), return_exceptions=True)
    assert results.count(True) == 1
    assert sum(isinstance(result, ApprovalAlreadyResolvedError) for result in results) == 1


async def test_wave2_concurrent_recovery_rolls_back_on_audit_failure(
    sessions: async_sessionmaker[AsyncSession],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_id, _ = await create_draft(sessions)
    provider = stub(generation_response())
    attempt = await SpecificationGenerationService(sessions, provider).start(
        request_id, expected_version=1
    )

    async def unavailable(*args: object, **kwargs: object) -> None:
        raise RuntimeError("Audit unavailable")

    async with sessions() as session:
        recovery = SpecificationRecoveryService(session)
        with monkeypatch.context() as patch:
            patch.setattr(AuditLogRepository, "log_event", unavailable)
            with pytest.raises(RuntimeError, match="Audit unavailable"):
                await recovery.recover()
        row = await session.get(GenerationAttempt, attempt.id)
        assert row is not None and row.status == "pending"
        repo = SpecificationVersionRepository(session)
        assert (await repo.get_request(request_id)).status == "generating"
    results = await asyncio.gather(recovery.recover(), recovery.recover())
    assert sorted(result["generations"] for result in results) == [0, 1]
    async with sessions() as session:
        events = list(
            await session.scalars(
                select(WorkflowAuditLog).where(
                    WorkflowAuditLog.event_type == "spec_generation_failed"
                )
            )
        )
        assert len(events) == 1
    provider.generate.assert_not_awaited()
