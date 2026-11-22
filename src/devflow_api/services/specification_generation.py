"""Generate immutable specification artifacts through the selected AIProvider."""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from devflow_api.adapters.exceptions import (
    MCPContextFailureError,
    MCPPermissionError,
    MCPServerNotFoundError,
    MCPToolSchemaError,
)
from devflow_api.adapters.mcp_adapter import MCPClientAdapter
from devflow_api.models.specification import (
    GenerationAttempt,
    SpecificationRequest,
    SpecificationVersion,
)
from devflow_api.providers.base import AIProvider
from devflow_api.providers.exceptions import ProviderError, ProviderMalformedResponseError
from devflow_api.repositories._workflow_transaction import immediate_transaction
from devflow_api.repositories.specification_version import SpecificationVersionRepository, text_hash
from devflow_api.schemas.ai_provider import ProviderResponse
from devflow_api.schemas.specification import (
    MCPContextRequest,
    SpecificationOutputSchema,
    SpecificationRequestCreate,
)
from devflow_api.services.specification_attempts import (
    ACTIVE,
    check_cancellation,
    generate_with_deadline,
    request_cancel,
    select_model,
)
from devflow_api.services.specification_prompts import generation_prompt
from devflow_api.services.specification_validation import validate_generation
from devflow_api.specification_errors import (
    ApprovedSpecificationError,
    AttemptConflictError,
    InvalidSpecTransitionError,
    MalformedSpecificationError,
    SpecificationCancelledError,
    SpecificationError,
    SpecificationNotFoundError,
)
from devflow_core.config import Settings, get_settings
from devflow_core.logging import get_logger


@dataclass(frozen=True)
class GenerationWork:
    draft: SpecificationRequestCreate
    request_id: int
    workflow_run_id: int | None
    provider_id: str
    model_id: str


class SpecificationGenerationService:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        provider: AIProvider,
        *,
        mcp: MCPClientAdapter | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._sessions = sessions
        self._provider = provider
        self._mcp = mcp
        self._settings = settings if settings is not None else get_settings()

    async def start(
        self,
        request_id: int,
        *,
        expected_version: int,
        provider_id: str | None = None,
        model: str | None = None,
    ) -> GenerationAttempt:
        model_id = select_model(self._provider, self._settings, provider_id, model)
        async with self._sessions() as session, immediate_transaction(session):
            repo = SpecificationVersionRepository(session, self._settings)
            request = await repo.get_request(request_id)
            version = await repo.current_version(request)
            if request.status == "approved" or version.status == "approved":
                raise ApprovedSpecificationError("Approved specification is immutable")
            active = await session.scalar(
                select(GenerationAttempt.id)
                .where(
                    GenerationAttempt.specification_request_id == request_id,
                    GenerationAttempt.status.in_(ACTIVE),
                )
                .limit(1)
            )
            if active is not None:
                raise AttemptConflictError("GENERATION_ALREADY_IN_PROGRESS")
            if request.current_version != expected_version or (
                request.status != "draft" or version.status != "draft"
            ):
                raise InvalidSpecTransitionError("Generation requires the current draft")
            attempt = GenerationAttempt(
                specification_request_id=request_id,
                specification_version_id=version.id,
                provider_id=self._provider.provider_id,
                model_id=model_id,
                prompt_hash="",
                status="pending",
            )
            request.status = "generating"
            request.provider_id = attempt.provider_id
            request.model_id = model_id
            session.add(attempt)
            await session.flush()
            return attempt

    async def cancel(self, attempt_id: int) -> None:
        await request_cancel(self._sessions, GenerationAttempt, attempt_id)

    async def run(
        self,
        attempt_id: int,
        contexts: Sequence[MCPContextRequest] = (),
        *,
        actor_id: str = "system",
    ) -> GenerationAttempt:
        work = await self._claim(attempt_id)
        if work is None:
            return await self.get_attempt(attempt_id)
        try:
            select_model(self._provider, self._settings, work.provider_id, work.model_id)
            await check_cancellation(self._sessions, GenerationAttempt, attempt_id)
            context, context_truncated = await self._context(work, attempt_id, contexts)
            prompt, truncated = generation_prompt(work.draft, context, self._settings)
            await self._record_prompt(attempt_id, text_hash(prompt), truncated or context_truncated)
            response = await generate_with_deadline(
                self._provider,
                self._settings,
                self._sessions,
                GenerationAttempt,
                attempt_id,
                prompt,
                work.model_id,
            )
            output = SpecificationOutputSchema.model_validate_json(response.content)
            validate_generation(output.artifacts())
            await self._finish(
                attempt_id, "succeeded", actor_id=actor_id, output=output, response=response
            )
        except asyncio.CancelledError:
            await self._finish(attempt_id, "cancelled", "PROVIDER_CANCELLED")
            raise
        except SpecificationCancelledError:
            await self._finish(attempt_id, "cancelled", "PROVIDER_CANCELLED")
        except (ValidationError, ProviderMalformedResponseError, MalformedSpecificationError):
            await self._finish(attempt_id, "failed", "MALFORMED_OUTPUT")
        except MCPContextFailureError:
            await self._finish(attempt_id, "failed", "MCP_CONTEXT_FAILURE")
        except TimeoutError:
            await self._finish(attempt_id, "failed", "PROVIDER_TIMEOUT")
        except ProviderError as exc:
            await self._finish(attempt_id, "failed", exc.error_code)
        except SpecificationError as exc:
            await self._finish(attempt_id, "failed", exc.code)
        except Exception:
            await self._finish(attempt_id, "failed", "INTERNAL_ERROR")
        return await self.get_attempt(attempt_id)

    async def get_attempt(self, attempt_id: int) -> GenerationAttempt:
        async with self._sessions() as session:
            return await self._get(session, attempt_id)

    async def _claim(self, attempt_id: int) -> GenerationWork | None:
        async with self._sessions() as session, immediate_transaction(session):
            attempt = await self._get(session, attempt_id)
            if attempt.status != "pending":
                return None
            repo = SpecificationVersionRepository(session, self._settings)
            request, version = await self._binding(repo, attempt)
            attempt.status = "running"
            attempt.started_at = datetime.now(UTC)
            await repo.audit(
                "spec_generation_started",
                request,
                version,
                attempt_id=attempt.id,
                provider_id=attempt.provider_id,
                model_id=attempt.model_id,
            )
            return GenerationWork(
                repo.draft_input(request),
                request.id,
                request.workflow_run_id,
                attempt.provider_id,
                attempt.model_id,
            )

    async def _context(
        self, work: GenerationWork, attempt_id: int, calls: Sequence[MCPContextRequest]
    ) -> tuple[str, bool]:
        if len(calls) > 16:
            raise MCPContextFailureError()
        text: list[str] = []
        truncated = False
        for call in calls:
            await check_cancellation(self._sessions, GenerationAttempt, attempt_id)
            try:
                if self._mcp is None:
                    raise MCPContextFailureError()
                chunk = await self._mcp.retrieve_context(
                    call.server,
                    call.tool,
                    call.arguments,
                    required=call.required,
                    specification_request_id=work.request_id,
                    workflow_run_id=work.workflow_run_id,
                )
                text.append(chunk.content)
                truncated |= chunk.truncated
            except (
                MCPContextFailureError,
                MCPPermissionError,
                MCPServerNotFoundError,
                MCPToolSchemaError,
            ):
                if call.required:
                    raise MCPContextFailureError() from None
                get_logger(__name__).warning("Optional specification context unavailable")
        return "\n".join(text), truncated

    async def _record_prompt(self, attempt_id: int, digest: str, truncated: bool) -> None:
        async with self._sessions() as session, immediate_transaction(session):
            attempt = await self._get(session, attempt_id)
            if attempt.cancellation_requested or attempt.status != "running":
                raise SpecificationCancelledError("Specification attempt cancelled")
            attempt.prompt_hash = digest
            attempt.context_truncated = int(truncated)
        if truncated:
            get_logger(__name__).warning("Specification context truncated", attempt_id=attempt_id)

    async def _finish(
        self,
        attempt_id: int,
        status: str,
        code: str | None = None,
        *,
        actor_id: str = "system",
        output: SpecificationOutputSchema | None = None,
        response: ProviderResponse | None = None,
    ) -> None:
        async with self._sessions() as session, immediate_transaction(session):
            attempt = await self._get(session, attempt_id)
            if attempt.status != "running":
                return
            repo = SpecificationVersionRepository(session, self._settings)
            request, version = await self._binding(repo, attempt)
            if attempt.cancellation_requested:
                status, code = "cancelled", "PROVIDER_CANCELLED"
            if status == "succeeded" and output is not None and response is not None:
                for kind, content in output.artifacts().items():
                    await repo.save_artifact(version.id, kind, content, commit=False)
                digest = await repo.compute_and_set_digest(version.id, commit=False)
                await repo.transition_status(version.id, "draft", "generated", commit=False)
                if response.usage is not None:
                    attempt.token_usage_json = response.usage.model_dump_json()
                await repo.audit(
                    "spec_generated",
                    request,
                    version,
                    attempt_id=attempt.id,
                    content_digest=digest,
                    context_truncated=bool(attempt.context_truncated),
                    actor_id=actor_id,
                )
            else:
                if request.status == "generating" and version.status == "draft":
                    request.status = "draft"
                attempt.error_code = code
                attempt.error_message = (
                    "Specification generation cancelled"
                    if status == "cancelled"
                    else "Specification generation failed"
                )
                await repo.audit(
                    "spec_generation_failed",
                    request,
                    version,
                    attempt_id=attempt.id,
                    error_code=code,
                    context_truncated=bool(attempt.context_truncated),
                    status=status,
                )
            attempt.status = status
            attempt.completed_at = datetime.now(UTC)

    @staticmethod
    async def _get(session: AsyncSession, attempt_id: int) -> GenerationAttempt:
        attempt = await session.get(GenerationAttempt, attempt_id)
        if attempt is None:
            raise SpecificationNotFoundError("Generation attempt not found")
        return attempt

    @staticmethod
    async def _binding(
        repo: SpecificationVersionRepository, attempt: GenerationAttempt
    ) -> tuple[SpecificationRequest, SpecificationVersion]:
        request = await repo.get_request(attempt.specification_request_id)
        if attempt.specification_version_id is None:
            raise InvalidSpecTransitionError("Generation attempt has no bound version")
        version = await repo.get_version(attempt.specification_version_id)
        if (
            version.specification_request_id != request.id
            or version.version_number != request.current_version
        ):
            raise InvalidSpecTransitionError("Generation attempt is bound to a stale version")
        return request, version
