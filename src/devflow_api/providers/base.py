"""Provider interface shared by generation and review callers."""

from typing import Protocol

from devflow_api.schemas.ai_provider import AvailabilityResult, GenerationOptions, ProviderResponse


class AIProvider(Protocol):
    provider_id: str
    model_id: str

    async def generate(
        self, prompt: str, options: GenerationOptions | None = None, *, model: str | None = None
    ) -> ProviderResponse: ...

    async def check_availability(self) -> AvailabilityResult: ...

    async def check_capability(self, capability: str) -> bool: ...
