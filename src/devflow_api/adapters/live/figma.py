"""Live Figma file adapter."""

from urllib.parse import quote

from devflow_api.adapters.exceptions import MissingCredentialError
from devflow_api.adapters.live._http import LiveHTTPAdapter
from devflow_api.adapters.protocols.figma import FigmaResponse
from devflow_core.config import Settings


class FigmaAdapter(LiveHTTPAdapter):
    def __init__(self, settings: Settings) -> None:
        super().__init__(
            "figma", "get_file", settings.FIGMA_API_BASE_URL, 10.0, credential_key="FIGMA_TOKEN"
        )
        self._token = settings.FIGMA_TOKEN

    def _headers(self) -> dict[str, str]:
        if not self._token:
            raise MissingCredentialError("figma", "FIGMA_TOKEN")
        return {"X-Figma-Token": self._token.get_secret_value()}

    async def get_file(self, file_key: str) -> FigmaResponse:
        self._headers()
        if file_key in {"", ".", ".."}:
            raise ValueError("Figma file key is required")
        await self._request("get_file", "GET", f"/v1/files/{quote(file_key, safe='')}")
        return FigmaResponse(stub=False)

    async def health_check(self) -> dict[str, str]:
        return await self._health("/v1/me")
