"""Cancellation, deadline, and provider selection shared by specification attempts."""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from devflow_api.models.specification import GenerationAttempt, ReviewAttempt
from devflow_api.providers.base import AIProvider
from devflow_api.providers.exceptions import ProviderConfigurationError
from devflow_api.repositories._workflow_transaction import immediate_transaction
from devflow_api.schemas.ai_provider import GenerationOptions, ProviderResponse
from devflow_api.specification_errors import (
    SpecificationCancelledError,
    SpecificationNotFoundError,
    TaskNotCancellableError,
)
from devflow_api.specification_security import redact_text
from devflow_core.config import Settings

ACTIVE = ("pending", "running")


def select_model(
    provider: AIProvider, settings: Settings, provider_id: str | None, model: str | None
) -> str:
    model_id = (provider.model_id if model is None else model).strip()
    key = settings.OPENAI_API_KEY
    if (
        provider.provider_id != settings.AI_PROVIDER
        or provider_id not in (None, provider.provider_id)
        or not 0 < len(model_id) <= 256
        or redact_text(model_id, settings) != model_id
        or (
            provider.provider_id == "openai" and (key is None or not key.get_secret_value().strip())
        )
    ):
        raise ProviderConfigurationError(settings.AI_PROVIDER, provider.model_id)
    return model_id


async def request_cancel[AttemptT: GenerationAttempt | ReviewAttempt](
    sessions: async_sessionmaker[AsyncSession], model: type[AttemptT], attempt_id: int
) -> None:
    async with sessions() as session, immediate_transaction(session):
        attempt = await session.get(model, attempt_id)
        if attempt is None:
            raise SpecificationNotFoundError("Specification attempt not found")
        if attempt.status not in ACTIVE:
            raise TaskNotCancellableError("Specification attempt is already terminal")
        attempt.cancellation_requested = 1


async def check_cancellation[AttemptT: GenerationAttempt | ReviewAttempt](
    sessions: async_sessionmaker[AsyncSession], model: type[AttemptT], attempt_id: int
) -> None:
    async with sessions() as session:
        attempt = await session.get(model, attempt_id)
        if attempt is None or attempt.cancellation_requested or attempt.status != "running":
            raise SpecificationCancelledError("Specification attempt cancelled")


async def generate_with_deadline[AttemptT: GenerationAttempt | ReviewAttempt](
    provider: AIProvider,
    settings: Settings,
    sessions: async_sessionmaker[AsyncSession],
    model: type[AttemptT],
    attempt_id: int,
    prompt: str,
    model_id: str,
) -> ProviderResponse:
    await check_cancellation(sessions, model, attempt_id)
    options = GenerationOptions(max_tokens=settings.AI_MAX_OUTPUT_TOKENS, json_output=True)
    async with asyncio.timeout(settings.AI_REQUEST_TIMEOUT_SECONDS):
        task = asyncio.create_task(provider.generate(prompt, options, model=model_id))
        try:
            while not task.done():
                await asyncio.wait({task}, timeout=0.15)
                await check_cancellation(sessions, model, attempt_id)
            return task.result()
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
