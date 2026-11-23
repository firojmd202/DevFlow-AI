"""Contracts for AI provider configuration and responses."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class ProviderConfig(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True, frozen=True)

    provider_id: Literal["ollama", "openai"]
    model_id: str = Field(min_length=1, max_length=256)
    base_url: str | None = None
    api_key: SecretStr | None = Field(default=None, exclude=True)
    timeout_seconds: int = Field(gt=0)
    max_retries: int = Field(ge=0)
    retry_budget_seconds: int = Field(ge=0)


class GenerationOptions(BaseModel):
    max_tokens: int | None = Field(default=None, gt=0)
    temperature: float | None = Field(default=None, ge=0, le=2)
    stop_sequences: list[Annotated[str, Field(min_length=1, max_length=256)]] = Field(
        default_factory=list, max_length=4
    )
    json_output: bool = False


class TokenUsage(BaseModel):
    model_config = ConfigDict(strict=True)

    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class ProviderResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    content: str = Field(min_length=1)
    model: str = Field(min_length=1)
    provider_id: str
    usage: TokenUsage | None = None
    finish_reason: str | None = None
    request_id: str | None = None


class AvailabilityResult(BaseModel):
    available: bool
    provider_id: str
    reason: str | None = None
    checked_at: datetime
