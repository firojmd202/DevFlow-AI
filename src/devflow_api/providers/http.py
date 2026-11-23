"""Shared HTTP transport, request limits, and retry policy for AI providers."""

import asyncio
import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime

import httpx
from pydantic import ValidationError

from devflow_api.providers.exceptions import (
    ProviderAuthError,
    ProviderConfigurationError,
    ProviderError,
    ProviderMalformedResponseError,
    ProviderQuotaError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from devflow_api.schemas.ai_provider import (
    AvailabilityResult,
    GenerationOptions,
    ProviderConfig,
    ProviderResponse,
)
from devflow_core.config import Settings

_MAX_RESPONSE_BYTES = 2 * 1024 * 1024


def _reject_nonfinite(_: str) -> None:
    raise ValueError("JSON numbers must be finite")


class HTTPProvider(ABC):
    provider_id: str

    def __init__(self, settings: Settings, config: ProviderConfig) -> None:
        self._config = config
        self.model_id = config.model_id
        self._max_prompt_tokens = settings.AI_MAX_PROMPT_TOKENS
        self._max_output_tokens = settings.AI_MAX_OUTPUT_TOKENS
        self._timeout = httpx.Timeout(config.timeout_seconds)
        self._health_timeout = config.timeout_seconds
        self._headers: dict[str, str] = {}

    async def generate(
        self, prompt: str, options: GenerationOptions | None = None, *, model: str | None = None
    ) -> ProviderResponse:
        model_id = self.model_id if model is None else model.strip()
        if (
            not 0 < len(model_id) <= 256
            or len(prompt) > 4 * self._max_prompt_tokens
            or not prompt.strip()
        ):
            raise ProviderConfigurationError(self.provider_id, self.model_id)
        options = options or GenerationOptions()
        try:
            async with asyncio.timeout(self._config.timeout_seconds):
                try:
                    return await self._generate_once(prompt, model_id, options)
                except (ProviderUnavailableError, ProviderRateLimitError) as exc:
                    if isinstance(exc, ProviderUnavailableError) and not exc.transient:
                        raise
                    first_error = exc

                if not self._config.retry_budget_seconds:
                    raise first_error
                try:
                    async with asyncio.timeout(self._config.retry_budget_seconds):
                        error = first_error
                        for attempt in range(self._config.max_retries):
                            await asyncio.sleep(2 ** min(attempt, 10))
                            try:
                                return await self._generate_once(prompt, model_id, options)
                            except (ProviderUnavailableError, ProviderRateLimitError) as exc:
                                if isinstance(exc, ProviderUnavailableError) and not exc.transient:
                                    raise
                                error = exc
                        raise error
                except TimeoutError:
                    raise ProviderTimeoutError(self.provider_id, model_id) from None
        except TimeoutError:
            raise ProviderTimeoutError(self.provider_id, model_id) from None

    async def _generate_once(
        self, prompt: str, model_id: str, options: GenerationOptions
    ) -> ProviderResponse:
        try:
            async with httpx.AsyncClient(timeout=self._timeout, trust_env=False) as client:
                async with client.stream(
                    "POST",
                    self._generation_url,
                    headers=self._headers,
                    json=self._payload(prompt, model_id, options),
                ) as response:
                    if response.status_code in (401, 403):
                        raise ProviderAuthError(self.provider_id, model_id)
                    if response.status_code == 429:
                        body = await self._read(response, model_id)
                        if self._is_quota_error(body):
                            raise ProviderQuotaError(self.provider_id, model_id)
                        raise ProviderRateLimitError(self.provider_id, model_id)
                    if not response.is_success:
                        raise ProviderUnavailableError(
                            self.provider_id, model_id, transient=response.status_code >= 500
                        )
                    data: object = json.loads(await self._read(response, model_id))
                    result = self._response(data, model_id, response.headers.get("x-request-id"))
                    if options.json_output and not isinstance(
                        json.loads(result.content, parse_constant=_reject_nonfinite), dict
                    ):
                        raise ProviderMalformedResponseError(self.provider_id, model_id)
                    return result
        except httpx.TimeoutException:
            raise ProviderTimeoutError(self.provider_id, model_id) from None
        except httpx.TransportError as exc:
            raise ProviderUnavailableError(
                self.provider_id, model_id, transient=isinstance(exc, httpx.ConnectError)
            ) from None
        except httpx.HTTPError:
            raise ProviderUnavailableError(self.provider_id, model_id) from None
        except (ValueError, KeyError, TypeError, IndexError, AttributeError, RecursionError):
            raise ProviderMalformedResponseError(self.provider_id, model_id) from None

    async def _read(self, response: httpx.Response, model_id: str) -> bytearray:
        body = bytearray()
        async for chunk in response.aiter_bytes(chunk_size=65536):
            if len(body) + len(chunk) > _MAX_RESPONSE_BYTES:
                raise ProviderMalformedResponseError(self.provider_id, model_id)
            body.extend(chunk)
        return body

    def _is_quota_error(self, body: bytearray) -> bool:
        return False

    def _max_tokens(self, options: GenerationOptions) -> int:
        return min(options.max_tokens or self._max_output_tokens, self._max_output_tokens)

    async def check_availability(self) -> AvailabilityResult:
        try:
            async with asyncio.timeout(self._health_timeout):
                async with httpx.AsyncClient(
                    timeout=self._health_timeout, trust_env=False
                ) as client:
                    async with client.stream(
                        "GET", self._health_url, headers=self._headers
                    ) as response:
                        available = response.is_success
            reason = None if available else "service or model unavailable"
        except (TimeoutError, httpx.HTTPError, ValueError, ProviderError):
            available = False
            reason = "health check failed"
        return AvailabilityResult(
            available=available,
            provider_id=self.provider_id,
            reason=reason,
            checked_at=datetime.now(UTC),
        )

    async def check_capability(self, capability: str) -> bool:
        return capability in {"generation", "structured_output"}

    @property
    @abstractmethod
    def _generation_url(self) -> str: ...

    @property
    @abstractmethod
    def _health_url(self) -> str: ...

    @abstractmethod
    def _payload(
        self, prompt: str, model_id: str, options: GenerationOptions
    ) -> dict[str, object]: ...

    @abstractmethod
    def _response(
        self, data: object, model_id: str, request_id: str | None
    ) -> ProviderResponse: ...


def provider_config(
    settings: Settings, provider_id: str, model_id: str, **options: object
) -> ProviderConfig:
    try:
        return ProviderConfig.model_validate(
            {
                "provider_id": provider_id,
                "model_id": model_id.strip(),
                "timeout_seconds": settings.AI_REQUEST_TIMEOUT_SECONDS,
                "max_retries": settings.AI_MAX_RETRIES,
                "retry_budget_seconds": settings.AI_RETRY_BUDGET_SECONDS,
                **options,
            }
        )
    except ValidationError:
        raise ProviderConfigurationError(provider_id, "") from None
