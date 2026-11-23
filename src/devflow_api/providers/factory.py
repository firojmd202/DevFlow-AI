"""Select the configured provider without importing the cloud provider by default."""

from devflow_api.providers.base import AIProvider
from devflow_api.providers.ollama_provider import OllamaProvider
from devflow_core.config import Settings


class ProviderFactory:
    @staticmethod
    def create(settings: Settings) -> AIProvider:
        if settings.AI_PROVIDER == "openai":
            from devflow_api.providers.openai_provider import OpenAIProvider  # noqa: PLC0415

            return OpenAIProvider(settings)
        return OllamaProvider(settings)
