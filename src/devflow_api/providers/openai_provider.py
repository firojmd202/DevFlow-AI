"""Explicitly enabled OpenAI Chat Completions provider."""

import json
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field

from devflow_api.providers.exceptions import ProviderConfigurationError
from devflow_api.providers.http import HTTPProvider, provider_config
from devflow_api.schemas.ai_provider import GenerationOptions, ProviderResponse, TokenUsage
from devflow_core.config import Settings


class CompletionMessage(BaseModel):
    model_config = ConfigDict(strict=True)

    content: str


class CompletionChoice(BaseModel):
    model_config = ConfigDict(strict=True)

    message: CompletionMessage
    finish_reason: str | None = None


class ChatCompletion(BaseModel):
    model_config = ConfigDict(strict=True)

    choices: list[CompletionChoice] = Field(min_length=1)
    model: str | None = None
    id: str | None = None
    usage: TokenUsage | None = None


class OpenAIProvider(HTTPProvider):
    provider_id = "openai"

    def __init__(self, settings: Settings) -> None:
        key = settings.OPENAI_API_KEY
        if settings.AI_PROVIDER != self.provider_id or key is None:
            raise ProviderConfigurationError(self.provider_id, settings.OPENAI_MODEL)
        secret = key.get_secret_value()
        if (
            not secret
            or not secret.isascii()
            or any(c.isspace() for c in secret)
            or not secret.isprintable()
        ):
            raise ProviderConfigurationError(self.provider_id, settings.OPENAI_MODEL)
        config = provider_config(settings, self.provider_id, settings.OPENAI_MODEL, api_key=key)
        super().__init__(settings, config)
        self._headers = {"Authorization": f"Bearer {secret}"}
        self._base_url = settings.OPENAI_API_BASE_URL

    @property
    def _generation_url(self) -> str:
        return f"{self._base_url}/chat/completions"

    @property
    def _health_url(self) -> str:
        return f"{self._base_url}/models/{quote(self.model_id, safe='')}"

    def _payload(self, prompt: str, model_id: str, options: GenerationOptions) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
            "max_completion_tokens": self._max_tokens(options),
        }
        if options.temperature is not None:
            payload["temperature"] = options.temperature
        if options.stop_sequences:
            payload["stop"] = options.stop_sequences
        if options.json_output:
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _is_quota_error(self, body: bytearray) -> bool:
        try:
            return bool(json.loads(body)["error"]["code"] == "insufficient_quota")
        except (ValueError, TypeError, KeyError, RecursionError):
            return False

    def _response(self, data: object, model_id: str, request_id: str | None) -> ProviderResponse:
        response = ChatCompletion.model_validate(data)
        choice = response.choices[0]
        return ProviderResponse(
            content=choice.message.content,
            model=response.model if response.model is not None else model_id,
            provider_id=self.provider_id,
            usage=response.usage,
            finish_reason=choice.finish_reason,
            request_id=request_id or response.id,
        )
