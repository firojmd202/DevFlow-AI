"""Serialized writes and immutable artifact storage for specification versions."""

import json
from datetime import UTC, datetime
from hashlib import sha256
from typing import cast

from sqlalchemy import CursorResult, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.models.specification import (
    ReviewAttempt,
    ReviewFinding,
    SpecificationArtifact,
    SpecificationRequest,
    SpecificationVersion,
)
from devflow_api.models.workflow_step_run import WorkflowStepRun
from devflow_api.repositories._workflow_transaction import immediate_transaction
from devflow_api.repositories.approval import AuditLogRepository
from devflow_api.schemas.specification import (
    ARTIFACT_TYPES,
    ArtifactType,
    SpecificationRequestCreate,
)
from devflow_api.schemas.workflow_template import canonical_hash, canonical_json
from devflow_api.specification_errors import (
    ApprovedSpecificationError,
    InvalidSpecTransitionError,
    SpecDigestMismatchError,
    SpecificationNotFoundError,
)
from devflow_api.specification_security import redact_text
from devflow_core.config import Settings, get_settings

_LIST_FIELDS = (
    "functional_requirements",
    "nonfunctional_constraints",
    "acceptance_criteria",
    "clarifying_questions",
)
_TRANSITIONS = {
    "draft": {"generated", "cancelled"},
    "generated": {"under_review", "cancelled"},
    "under_review": {"generated", "revision_required", "ready_for_approval", "cancelled"},
    "revision_required": {"cancelled"},
    "ready_for_approval": {"revision_required", "cancelled"},
}


def text_hash(content: str) -> str:
    return sha256(content.encode("utf-8")).hexdigest()


def artifact_digest(artifacts: dict[ArtifactType, str]) -> str:
    return text_hash("\n---\n".join(artifacts[kind] for kind in ARTIFACT_TYPES))


class SpecificationVersionRepository:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings if settings is not None else get_settings()

    async def create_request(
        self,
        draft: SpecificationRequestCreate,
        *,
        actor_id: str,
        supersedes_version_id: int | None = None,
        commit: bool = True,
    ) -> SpecificationRequest:
        async with immediate_transaction(self.session, commit=commit):
            await self._validate_workflow_binding(draft)
            if supersedes_version_id is not None:
                previous = await self.get_version(supersedes_version_id)
                if previous.status != "approved":
                    raise InvalidSpecTransitionError(
                        "Only approved specifications can be superseded"
                    )
                if not await self.verify_digest(previous.id):
                    raise SpecDigestMismatchError("Superseded approval has an invalid digest")
            values, digest = self._draft_values(draft)
            request = SpecificationRequest(
                **values, status="draft", current_version=1, content_hash=digest
            )
            self.session.add(request)
            await self.session.flush()
            version = await self._insert_version(request, 1, supersedes_version_id)
            await self.audit(
                "spec_draft_created", request, version, actor_id=actor_id, actor="user"
            )
            return request

    async def get_request(self, request_id: int) -> SpecificationRequest:
        request = await self.session.get(SpecificationRequest, request_id, populate_existing=True)
        if request is None:
            raise SpecificationNotFoundError("Specification request not found")
        return request

    async def get_version(self, version_id: int) -> SpecificationVersion:
        version = await self.session.get(SpecificationVersion, version_id, populate_existing=True)
        if version is None:
            raise SpecificationNotFoundError("Specification version not found")
        return version

    async def current_version(self, request: SpecificationRequest) -> SpecificationVersion:
        version = await self.session.scalar(
            select(SpecificationVersion)
            .where(
                SpecificationVersion.specification_request_id == request.id,
                SpecificationVersion.version_number == request.current_version,
            )
            .execution_options(populate_existing=True)
        )
        if version is None:
            raise SpecificationNotFoundError("Current specification version not found")
        return version

    async def update_request(
        self,
        request_id: int,
        draft: SpecificationRequestCreate,
        *,
        expected_version: int,
        actor_id: str,
        commit: bool = True,
    ) -> SpecificationRequest:
        async with immediate_transaction(self.session, commit=commit):
            request = await self.get_request(request_id)
            prior = await self.current_version(request)
            if prior.status == "approved":
                raise ApprovedSpecificationError("Start a new request to supersede an approval")
            self._check_revision(request, expected_version)
            if (request.workflow_run_id, request.workflow_step_id) != (
                draft.workflow_run_id,
                draft.workflow_step_id,
            ):
                raise InvalidSpecTransitionError("Draft revisions cannot change workflow binding")
            values, digest = self._draft_values(draft)
            version = await self._insert_version(request, expected_version + 1, prior.id)
            for key, value in values.items():
                setattr(request, key, value)
            request.content_hash = digest
            request.current_version = version.version_number
            request.status = "draft"
            await self.audit(
                "spec_request_updated",
                request,
                version,
                actor="user",
                actor_id=actor_id,
                prior_version=expected_version,
                new_version=version.version_number,
                content_hash=digest,
            )
            await self.audit(
                "spec_revision_created",
                request,
                version,
                actor="user",
                actor_id=actor_id,
                prior_version=expected_version,
                new_version=version.version_number,
            )
            return request

    async def create_version(
        self,
        request_id: int,
        version_number: int,
        *,
        actor_id: str,
        commit: bool = True,
    ) -> SpecificationVersion:
        async with immediate_transaction(self.session, commit=commit):
            request = await self.get_request(request_id)
            await self.update_request(
                request_id,
                self.draft_input(request),
                expected_version=version_number - 1,
                actor_id=actor_id,
                commit=False,
            )
            return await self.current_version(request)

    async def transition_status(
        self,
        version_id: int,
        from_status: str,
        to_status: str,
        *,
        commit: bool = True,
    ) -> SpecificationVersion:
        async with immediate_transaction(self.session, commit=commit):
            version = await self.get_version(version_id)
            request = await self.get_request(version.specification_request_id)
            if version.status == "approved":
                raise ApprovedSpecificationError("Approved specification is immutable")
            if (
                version.version_number != request.current_version
                or version.status != from_status
                or to_status not in _TRANSITIONS.get(from_status, set())
                or (request.status == "generating" and to_status != "generated")
            ):
                raise InvalidSpecTransitionError("Invalid specification state transition")
            if (
                from_status == "draft"
                and to_status == "generated"
                and not await self.verify_digest(version_id)
            ):
                raise SpecDigestMismatchError(
                    "Generated version requires a verified artifact digest"
                )
            result = cast(
                CursorResult[object],
                await self.session.execute(
                    update(SpecificationVersion)
                    .where(
                        SpecificationVersion.id == version_id,
                        SpecificationVersion.status == from_status,
                    )
                    .values(status=to_status, updated_at=datetime.now(UTC))
                ),
            )
            if result.rowcount != 1:
                raise InvalidSpecTransitionError("Specification state changed concurrently")
            request.status = to_status
            return version

    async def save_artifact(
        self,
        version_id: int,
        artifact_type: ArtifactType,
        content: str,
        *,
        commit: bool = True,
    ) -> SpecificationArtifact:
        async with immediate_transaction(self.session, commit=commit):
            version = await self.get_version(version_id)
            request = await self.get_request(version.specification_request_id)
            if version.status == "approved":
                raise ApprovedSpecificationError("Approved artifacts are immutable")
            if (
                version.status != "draft"
                or version.content_digest is not None
                or version.version_number != request.current_version
                or await self.get_artifact(version_id, artifact_type) is not None
            ):
                raise InvalidSpecTransitionError("Artifact cannot be overwritten")
            safe_content = redact_text(content, self.settings)
            artifact = SpecificationArtifact(
                specification_version_id=version_id,
                artifact_type=artifact_type,
                content=safe_content,
                content_hash=text_hash(safe_content),
            )
            self.session.add(artifact)
            await self.session.flush()
            return artifact

    async def get_artifact(
        self,
        version_id: int,
        artifact_type: ArtifactType,
    ) -> SpecificationArtifact | None:
        return await self.session.scalar(
            select(SpecificationArtifact)
            .where(
                SpecificationArtifact.specification_version_id == version_id,
                SpecificationArtifact.artifact_type == artifact_type,
            )
            .execution_options(populate_existing=True)
        )

    async def artifact_contents(self, version_id: int) -> dict[ArtifactType, str]:
        rows = await self._artifacts(version_id)
        return {cast(ArtifactType, row.artifact_type): row.content for row in rows}

    async def _artifacts(self, version_id: int) -> list[SpecificationArtifact]:
        return list(
            await self.session.scalars(
                select(SpecificationArtifact)
                .where(SpecificationArtifact.specification_version_id == version_id)
                .execution_options(populate_existing=True)
            )
        )

    async def compute_and_set_digest(self, version_id: int, *, commit: bool = True) -> str:
        async with immediate_transaction(self.session, commit=commit):
            version = await self.get_version(version_id)
            artifacts = await self.artifact_contents(version_id)
            if set(artifacts) != set(ARTIFACT_TYPES):
                raise SpecDigestMismatchError("Specification artifacts are incomplete")
            digest = artifact_digest(artifacts)
            if version.content_digest == digest:
                return digest
            if version.content_digest is not None or version.status != "draft":
                raise SpecDigestMismatchError("Specification digest is immutable")
            version.content_digest = digest
            await self.session.flush()
            return digest

    async def verify_digest(self, version_id: int) -> bool:
        version = await self.get_version(version_id)
        rows = await self._artifacts(version_id)
        if any(text_hash(row.content) != row.content_hash for row in rows):
            return False
        artifacts = {cast(ArtifactType, row.artifact_type): row.content for row in rows}
        return set(artifacts) == set(ARTIFACT_TYPES) and (
            artifact_digest(artifacts) == version.content_digest
        )

    async def list_versions(self, request_id: int) -> list[SpecificationVersion]:
        return list(
            await self.session.scalars(
                select(SpecificationVersion)
                .where(
                    SpecificationVersion.specification_request_id == request_id,
                )
                .order_by(SpecificationVersion.version_number)
            )
        )

    async def list_requests(self) -> list[SpecificationRequest]:
        return list(
            await self.session.scalars(
                select(SpecificationRequest).order_by(SpecificationRequest.id)
            )
        )

    async def list_reviews(self, version_id: int) -> list[ReviewAttempt]:
        return list(
            await self.session.scalars(
                select(ReviewAttempt)
                .where(
                    ReviewAttempt.specification_version_id == version_id,
                )
                .order_by(ReviewAttempt.id)
            )
        )

    async def list_findings(self, review_id: int) -> list[ReviewFinding]:
        return list(
            await self.session.scalars(
                select(ReviewFinding)
                .where(
                    ReviewFinding.review_attempt_id == review_id,
                )
                .order_by(ReviewFinding.id)
            )
        )

    async def audit(
        self,
        event: str,
        request: SpecificationRequest,
        version: SpecificationVersion,
        *,
        actor: str = "system",
        **details: object,
    ) -> None:
        payload = {
            "specification_request_id": request.id,
            "specification_version_id": version.id,
            **{
                key: redact_text(value, self.settings) if isinstance(value, str) else value
                for key, value in details.items()
            },
        }
        await AuditLogRepository(self.session).log_event(
            event, actor, request.workflow_run_id, payload, commit=False
        )

    @staticmethod
    def draft_input(request: SpecificationRequest) -> SpecificationRequestCreate:
        values = {name: getattr(request, name) for name in SpecificationRequestCreate.model_fields}
        for key in _LIST_FIELDS:
            values[key] = json.loads(values[key]) if values[key] is not None else []
        return SpecificationRequestCreate.model_validate(values)

    def _draft_values(self, draft: SpecificationRequestCreate) -> tuple[dict[str, object], str]:
        values: dict[str, object] = draft.model_dump(mode="json")
        for key, value in values.items():
            if isinstance(value, str):
                values[key] = redact_text(value, self.settings)
            elif isinstance(value, list):
                values[key] = [redact_text(str(item), self.settings) for item in value]
        digest = canonical_hash(values)
        for key in _LIST_FIELDS:
            values[key] = canonical_json(values[key])
        return values, digest

    async def _validate_workflow_binding(self, draft: SpecificationRequestCreate) -> None:
        if draft.workflow_step_id is not None:
            step = await self.session.get(WorkflowStepRun, draft.workflow_step_id)
            if step is None or step.workflow_run_id != draft.workflow_run_id:
                raise InvalidSpecTransitionError(
                    "Workflow step does not belong to the specified run"
                )

    @staticmethod
    def _check_revision(request: SpecificationRequest, expected_version: int) -> None:
        if request.status == "approved":
            raise ApprovedSpecificationError("Start a new request to supersede an approved version")
        if request.status not in {"draft", "revision_required"} or (
            request.current_version != expected_version
        ):
            raise InvalidSpecTransitionError("Draft cannot be revised from the current state")

    async def _insert_version(
        self,
        request: SpecificationRequest,
        number: int,
        previous: int | None,
    ) -> SpecificationVersion:
        version = SpecificationVersion(
            specification_request_id=request.id,
            version_number=number,
            status="draft",
            supersedes_version_id=previous,
        )
        self.session.add(version)
        await self.session.flush()
        return version
