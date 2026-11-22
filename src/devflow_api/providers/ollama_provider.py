"""Local Ollama generation through its HTTP API."""

import httpx
from pydantic import BaseModel, ConfigDict

from devflow_api.providers.exceptions import ProviderConfigurationError
from devflow_api.providers.http import HTTPProvider, provider_config
from devflow_api.schemas.ai_provider import GenerationOptions, ProviderResponse, TokenUsage
from devflow_core.config import Settings


class OllamaGeneration(BaseModel):
    model_config = ConfigDict(strict=True)

    response: str
    model: str | None = None
    done_reason: str | None = None
    prompt_eval_count: int | None = None
    eval_count: int | None = None


class OllamaProvider(HTTPProvider):
    provider_id = "ollama"

    def __init__(self, settings: Settings) -> None:
        try:
            url = httpx.URL(settings.OLLAMA_BASE_URL)
        except httpx.InvalidURL:
            raise ProviderConfigurationError(self.provider_id, settings.OLLAMA_MODEL) from None
        host = url.host.rstrip(".").lower()
        if (
            url.scheme not in {"http", "https"}
            or not url.host
            or url.userinfo
            or url.query
            or url.fragment
            or host == "openai.com"
            or host.endswith(".openai.com")
        ):
            raise ProviderConfigurationError(self.provider_id, settings.OLLAMA_MODEL)
        self._base_url = str(url).rstrip("/")
        config = provider_config(
            settings, self.provider_id, settings.OLLAMA_MODEL, base_url=self._base_url
        )
        super().__init__(settings, config)
        self._timeout = httpx.Timeout(
            config.timeout_seconds, connect=settings.OLLAMA_TIMEOUT_SECONDS
        )
        self._health_timeout = min(settings.OLLAMA_TIMEOUT_SECONDS, config.timeout_seconds)

    @property
    def _generation_url(self) -> str:
        return f"{self._base_url}/api/generate"

    @property
    def _health_url(self) -> str:
        return f"{self._base_url}/api/tags"

    def _payload(self, prompt: str, model_id: str, options: GenerationOptions) -> dict[str, object]:
        parameters: dict[str, object] = {"num_predict": self._max_tokens(options)}
        if options.temperature is not None:
            parameters["temperature"] = options.temperature
        if options.stop_sequences:
            parameters["stop"] = options.stop_sequences
        payload: dict[str, object] = {
            "model": model_id,
            "prompt": prompt,
            "stream": False,
            "options": parameters,
        }
        if options.json_output:
            payload["format"] = "json"
        return payload

    def _response(self, data: object, model_id: str, request_id: str | None) -> ProviderResponse:
        response = OllamaGeneration.model_validate(data)
        prompt_tokens = response.prompt_eval_count
        completion_tokens = response.eval_count
        usage = None
        if prompt_tokens is not None or completion_tokens is not None:
            usage = TokenUsage(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
            if usage.prompt_tokens is not None and usage.completion_tokens is not None:
                usage.total_tokens = usage.prompt_tokens + usage.completion_tokens
        return ProviderResponse(
            content=response.response,
            model=response.model if response.model is not None else model_id,
            provider_id=self.provider_id,
            usage=usage,
            finish_reason=response.done_reason,
            request_id=request_id,
        )
