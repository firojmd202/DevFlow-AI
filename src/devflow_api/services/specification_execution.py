"""Wire approved specification services into Wave 1 executor dispatch."""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from devflow_api.adapters.mcp_adapter import MCPClientAdapter
from devflow_api.executors.specification import (
    GeneratorInput,
    ReviewerInput,
    SpecGeneratorExecutor,
    SpecReviewerExecutor,
)
from devflow_api.models.specification import GenerationAttempt, ReviewAttempt
from devflow_api.providers.factory import ProviderFactory
from devflow_api.repositories.approval import AuditLogRepository
from devflow_api.repositories.specification_version import SpecificationVersionRepository, text_hash
from devflow_api.schemas.executor import ExecutionContext
from devflow_api.services.specification_generation import SpecificationGenerationService
from devflow_api.services.specification_review import SpecificationReviewService
from devflow_api.specification_errors import AttemptConflictError, SpecificationError
from devflow_core.config import Settings


class SpecificationExecution:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self.sessions = sessions
        self.settings = settings

    def executors(self) -> tuple[SpecGeneratorExecutor, SpecReviewerExecutor]:
        return SpecGeneratorExecutor(self.generate), SpecReviewerExecutor(self.review)

    async def generate(self, context: ExecutionContext) -> dict[str, object]:
        inputs = GeneratorInput.model_validate(context.inputs)
        contexts = tuple(item.model_copy(deep=True) for item in inputs.mcp_contexts)
        async with self.sessions() as session:
            repo = SpecificationVersionRepository(session, self.settings)
            request = await repo.get_request(inputs.spec_request_id)
            if request.workflow_run_id not in (None, context.run_id):
                raise SpecificationError("Specification is not bound to this workflow run")
            version = await repo.current_version(request)
            prior = await session.scalar(
                select(GenerationAttempt)
                .where(
                    GenerationAttempt.specification_version_id == version.id,
                )
                .order_by(GenerationAttempt.id.desc())
                .limit(1)
            )
        if prior is None:
            async with self.sessions() as audit_session:
                service = SpecificationGenerationService(
                    self.sessions,
                    ProviderFactory.create(self.settings),
                    mcp=MCPClientAdapter.from_settings(
                        AuditLogRepository(audit_session), self.settings
                    ),
                    settings=self.settings,
                )
                prior = await service.start(
                    request.id,
                    expected_version=version.version_number,
                    provider_id=request.provider_id,
                    model=request.model_id,
                )
                prior = await service.run(
                    prior.id, contexts, actor_id=context.actor_id, workflow_run_id=context.run_id
                )
            if prior.status != "succeeded":
                raise AttemptConflictError(prior.error_code or "GENERATION_NOT_COMPLETE")
        elif prior.status != "succeeded" or contexts:
            # Existing attempts may belong to another submitter with a different context plan.
            raise AttemptConflictError(prior.error_code or "GENERATION_NOT_COMPLETE")
        async with self.sessions() as session:
            repo = SpecificationVersionRepository(session, self.settings)
            if not await repo.verify_digest(version.id):
                raise SpecificationError("Specification digest did not verify")
            artifacts = await repo.artifact_contents(version.id)
        return {
            "artifacts": [
                {
                    "name": f"{kind}.md",
                    "digest": text_hash(content),
                    "uri": (
                        f"/api/v1/specification-requests/{request.id}"
                        f"/versions/{version.id}/artifacts/{kind}"
                    ),
                }
                for kind, content in artifacts.items()
            ]
        }

    async def review(self, context: ExecutionContext) -> dict[str, object]:
        inputs = ReviewerInput.model_validate(context.inputs)
        async with self.sessions() as session:
            repo = SpecificationVersionRepository(session, self.settings)
            version = await repo.get_version(inputs.spec_version_id)
            request = await repo.get_request(version.specification_request_id)
            if (
                request.workflow_run_id not in (None, context.run_id)
                or version.version_number != request.current_version
            ):
                raise SpecificationError(
                    "Specification version is not current for this workflow run"
                )
            if not await repo.verify_digest(version.id):
                raise SpecificationError("Specification digest did not verify")
            prior = await session.scalar(
                select(ReviewAttempt)
                .where(
                    ReviewAttempt.specification_version_id == version.id,
                )
                .order_by(ReviewAttempt.id.desc())
                .limit(1)
            )
        if prior is None or prior.status != "succeeded":
            service = SpecificationReviewService(
                self.sessions,
                ProviderFactory.create(self.settings),
                settings=self.settings,
            )
            if prior is None:
                prior = await service.start(version.id)
            if prior.status == "pending":
                prior = await service.run(prior.id)
        if prior.status != "succeeded" or prior.error_code:
            raise AttemptConflictError(prior.error_code or "REVIEW_NOT_COMPLETE")
        counts: object = json.loads(prior.finding_count_by_severity or "{}")
        return {"finding_count_by_severity": counts}
