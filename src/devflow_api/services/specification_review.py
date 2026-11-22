"""Run deterministic and advisory AI reviews of an immutable specification version."""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from devflow_api.models.specification import (
    ReviewAttempt,
    SpecificationRequest,
    SpecificationVersion,
)
from devflow_api.models.specification import ReviewFinding as FindingRow
from devflow_api.providers.base import AIProvider
from devflow_api.providers.exceptions import ProviderError, ProviderMalformedResponseError
from devflow_api.repositories._workflow_transaction import immediate_transaction
from devflow_api.repositories.specification_version import (
    SpecificationVersionRepository,
    artifact_digest,
)
from devflow_api.schemas.specification import (
    AI_REVIEW_DISCLAIMER,
    SEVERITIES,
    ArtifactType,
    ReviewFinding,
    ReviewOutputSchema,
)
from devflow_api.schemas.workflow_template import canonical_json
from devflow_api.services.specification_attempts import (
    ACTIVE,
    check_cancellation,
    generate_with_deadline,
    request_cancel,
    select_model,
)
from devflow_api.services.specification_prompts import review_prompt
from devflow_api.services.specification_validation import (
    deterministic_findings,
    malformed_review_finding,
)
from devflow_api.specification_errors import (
    ApprovedSpecificationError,
    AttemptConflictError,
    InvalidSpecTransitionError,
    SpecDigestMismatchError,
    SpecificationCancelledError,
    SpecificationError,
    SpecificationNotFoundError,
)
from devflow_api.specification_security import redact_text
from devflow_core.config import Settings, get_settings


@dataclass(frozen=True)
class ReviewWork:
    artifacts: dict[ArtifactType, str]
    provider_id: str
    model_id: str


class SpecificationReviewService:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        provider: AIProvider,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._sessions = sessions
        self._provider = provider
        self._settings = settings if settings is not None else get_settings()

    async def start(
        self,
        version_id: int,
        *,
        provider_id: str | None = None,
        model: str | None = None,
    ) -> ReviewAttempt:
        model_id = select_model(self._provider, self._settings, provider_id, model)
        async with self._sessions() as session, immediate_transaction(session):
            repo = SpecificationVersionRepository(session, self._settings)
            version = await repo.get_version(version_id)
            if version.status == "approved":
                raise ApprovedSpecificationError("Approved specification is immutable")
            active = await session.scalar(
                select(ReviewAttempt.id)
                .where(
                    ReviewAttempt.specification_version_id == version_id,
                    ReviewAttempt.status.in_(ACTIVE),
                )
                .limit(1)
            )
            if active is not None:
                raise AttemptConflictError("REVIEW_ALREADY_IN_PROGRESS")
            if version.status != "generated":
                raise InvalidSpecTransitionError("Review requires the current generated version")
            if not await repo.verify_digest(version_id) or version.content_digest is None:
                raise SpecDigestMismatchError("Review requires a verified artifact digest")
            attempt = ReviewAttempt(
                specification_version_id=version_id,
                provider_id=self._provider.provider_id,
                model_id=model_id,
                artifact_hash=version.content_digest,
                status="pending",
            )
            await repo.transition_status(version_id, "generated", "under_review", commit=False)
            session.add(attempt)
            await session.flush()
            return attempt

    async def cancel(self, attempt_id: int) -> None:
        await request_cancel(self._sessions, ReviewAttempt, attempt_id)

    async def request_revision(self, version_id: int, *, actor_id: str) -> None:
        async with self._sessions() as session, immediate_transaction(session):
            repo = SpecificationVersionRepository(session, self._settings)
            version = await repo.transition_status(
                version_id, "under_review", "revision_required", commit=False
            )
            request = await repo.get_request(version.specification_request_id)
            active = await session.scalar(
                select(ReviewAttempt)
                .where(
                    ReviewAttempt.specification_version_id == version_id,
                    ReviewAttempt.status.in_(ACTIVE),
                )
                .limit(1)
            )
            if active is not None:
                active.status = "cancelled"
                active.cancellation_requested = 1
                active.completed_at = datetime.now(UTC)
                await repo.audit(
                    "spec_review_failed",
                    request,
                    version,
                    actor="user",
                    actor_id=actor_id,
                    attempt_id=active.id,
                    status="cancelled",
                    reason="revision_requested",
                )

    async def run(self, attempt_id: int) -> ReviewAttempt:
        work = await self._claim(attempt_id)
        if work is None:
            return await self.get_attempt(attempt_id)
        findings: list[ReviewFinding] = []
        try:
            await check_cancellation(self._sessions, ReviewAttempt, attempt_id)
            findings = deterministic_findings(work.artifacts)
            malformed = False
            if not any(finding.severity == "Critical" for finding in findings):
                select_model(self._provider, self._settings, work.provider_id, work.model_id)
                try:
                    findings.extend(await self._semantic_findings(attempt_id, work))
                except (ProviderMalformedResponseError, ValidationError):
                    findings.append(malformed_review_finding())
                    malformed = True
            await self._finish(
                attempt_id,
                "succeeded",
                findings,
                "AI_REVIEW_MALFORMED" if malformed else None,
            )
        except asyncio.CancelledError:
            await self._finish(attempt_id, "cancelled", [], "PROVIDER_CANCELLED")
            raise
        except SpecificationCancelledError:
            await self._finish(attempt_id, "cancelled", [], "PROVIDER_CANCELLED")
        except TimeoutError:
            await self._finish(attempt_id, "failed", findings, "PROVIDER_TIMEOUT")
        except ProviderError as exc:
            await self._finish(attempt_id, "failed", findings, exc.error_code)
        except SpecificationError as exc:
            await self._finish(attempt_id, "failed", findings, exc.code)
        except Exception:
            await self._finish(attempt_id, "failed", [], "INTERNAL_ERROR")
        return await self.get_attempt(attempt_id)

    async def get_attempt(self, attempt_id: int) -> ReviewAttempt:
        async with self._sessions() as session:
            return await self._get(session, attempt_id)

    async def _claim(self, attempt_id: int) -> ReviewWork | None:
        async with self._sessions() as session, immediate_transaction(session):
            attempt = await self._get(session, attempt_id)
            if attempt.status != "pending":
                return None
            repo = SpecificationVersionRepository(session, self._settings)
            request, version = await self._binding(repo, attempt)
            if version.status != "under_review":
                raise InvalidSpecTransitionError("Review attempt is no longer active")
            attempt.status = "running"
            attempt.started_at = datetime.now(UTC)
            await repo.audit(
                "spec_review_started",
                request,
                version,
                attempt_id=attempt.id,
                provider_id=attempt.provider_id,
                model_id=attempt.model_id,
            )
            return ReviewWork(
                await repo.artifact_contents(version.id), attempt.provider_id, attempt.model_id
            )

    async def _semantic_findings(self, attempt_id: int, work: ReviewWork) -> list[ReviewFinding]:
        response = await generate_with_deadline(
            self._provider,
            self._settings,
            self._sessions,
            ReviewAttempt,
            attempt_id,
            review_prompt(work.artifacts, self._settings),
            work.model_id,
        )
        output = ReviewOutputSchema.model_validate_json(response.content)
        findings = []
        for item in output.findings:
            recommendation = f"{item.recommendation}\n\n{AI_REVIEW_DISCLAIMER}"
            findings.append(
                ReviewFinding(
                    severity=item.severity,
                    dimension=item.dimension,
                    finding_text=item.finding_text,
                    location=item.location,
                    recommendation=recommendation,
                    source="ai",
                )
            )
        return findings

    async def _finish(
        self,
        attempt_id: int,
        status: str,
        findings: list[ReviewFinding],
        code: str | None,
    ) -> None:
        async with self._sessions() as session, immediate_transaction(session):
            attempt = await self._get(session, attempt_id)
            if attempt.status != "running":
                return
            repo = SpecificationVersionRepository(session, self._settings)
            request, version = await self._binding(repo, attempt)
            if attempt.cancellation_requested:
                status, code, findings = "cancelled", "PROVIDER_CANCELLED", []
            if status == "succeeded":
                artifacts = await repo.artifact_contents(version.id)
                if not await repo.verify_digest(version.id) or (
                    artifact_digest(artifacts) != attempt.artifact_hash
                ):
                    raise SpecDigestMismatchError("Specification changed during review")
            counts = {severity: 0 for severity in SEVERITIES}
            for finding in findings:
                counts[finding.severity] += 1
                session.add(
                    FindingRow(
                        review_attempt_id=attempt.id,
                        specification_version_id=version.id,
                        severity=finding.severity,
                        dimension=finding.dimension,
                        source=finding.source,
                        finding_text=redact_text(finding.finding_text, self._settings),
                        location=redact_text(finding.location, self._settings),
                        recommendation=redact_text(finding.recommendation, self._settings),
                    )
                )
            next_status = "generated"
            if status == "succeeded":
                next_status = "revision_required" if counts["Critical"] else "ready_for_approval"
            if version.status == "under_review":
                await repo.transition_status(version.id, "under_review", next_status, commit=False)
            attempt.status = status
            attempt.completed_at = datetime.now(UTC)
            attempt.finding_count_by_severity = canonical_json(counts)
            attempt.error_code = code
            await repo.audit(
                "spec_review_completed" if status == "succeeded" else "spec_review_failed",
                request,
                version,
                attempt_id=attempt.id,
                finding_count_by_severity=counts,
                error_code=code,
                status=status,
            )

    @staticmethod
    async def _get(session: AsyncSession, attempt_id: int) -> ReviewAttempt:
        attempt = await session.get(ReviewAttempt, attempt_id)
        if attempt is None:
            raise SpecificationNotFoundError("Review attempt not found")
        return attempt

    @staticmethod
    async def _binding(
        repo: SpecificationVersionRepository,
        attempt: ReviewAttempt,
    ) -> tuple[SpecificationRequest, SpecificationVersion]:
        version = await repo.get_version(attempt.specification_version_id)
        request = await repo.get_request(version.specification_request_id)
        return request, version
