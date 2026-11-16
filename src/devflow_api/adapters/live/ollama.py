"""Live adapter for a configured Ollama server."""

from devflow_api.adapters.live._http import LiveHTTPAdapter
from devflow_api.adapters.protocols.ollama import OllamaResponse
from devflow_core.config import Settings


class OllamaAdapter(LiveHTTPAdapter):
    def __init__(self, settings: Settings) -> None:
        super().__init__(
            "ollama", "generate", settings.OLLAMA_BASE_URL, float(settings.OLLAMA_TIMEOUT_SECONDS)
        )

    async def generate(self, model: str, prompt: str) -> OllamaResponse:
        await self._request(
            "generate",
            "POST",
            "/api/generate",
            payload={"model": model, "prompt": prompt, "stream": False},
        )
        return OllamaResponse(stub=False)

    async def health_check(self) -> dict[str, str]:
        return await self._health("/api/tags")
