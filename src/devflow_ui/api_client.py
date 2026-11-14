"""HTTP boundary for Streamlit's backend requests."""

import logging

import httpx

logger = logging.getLogger(__name__)


class APIClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def get_health(self) -> dict[str, str] | None:
        try:
            async with httpx.AsyncClient(timeout=3.0, trust_env=False) as client:
                response = await client.get(f"{self.base_url}/health")
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, httpx.InvalidURL, ValueError):
            logger.warning("Backend health request failed")
            return None

        if not isinstance(data, dict):
            logger.warning("Backend health response is invalid")
            return None
        status = data.get("status")
        version = data.get("version")
        if not isinstance(status, str) or not isinstance(version, str):
            logger.warning("Backend health response is invalid")
            return None
        return {"status": status, "version": version}
