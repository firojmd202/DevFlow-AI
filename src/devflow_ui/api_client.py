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

    async def _project_request(
        self,
        method: str,
        path: str = "",
        *,
        params: dict[str, str | int] | None = None,
        payload: dict[str, object] | None = None,
    ) -> object:
        try:
            async with httpx.AsyncClient(timeout=3.0, trust_env=False) as client:
                response = await client.request(
                    method, f"{self.base_url}/api/v1/projects{path}", params=params, json=payload
                )
                response.raise_for_status()
                if method == "DELETE":
                    return response.status_code == 204
                return response.json()
        except (httpx.HTTPError, httpx.InvalidURL, ValueError):
            logger.warning("Project request failed")
            return None

    async def list_projects(
        self, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[dict[str, object]] | None:
        params: dict[str, str | int] = {"limit": limit, "offset": offset}
        if status is not None:
            params["status"] = status
        data = await self._project_request("GET", params=params)
        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            return None
        return list(data)

    async def create_project(
        self, name: str, description: str | None = None, tags: list[str] | None = None
    ) -> dict[str, object] | None:
        data = await self._project_request(
            "POST", payload={"name": name, "description": description, "tags": tags or []}
        )
        return data if isinstance(data, dict) else None

    async def update_project(self, project_id: int, **fields: object) -> dict[str, object] | None:
        data = await self._project_request("PUT", f"/{project_id}", payload=fields)
        return data if isinstance(data, dict) else None

    async def delete_project(self, project_id: int) -> bool:
        return await self._project_request("DELETE", f"/{project_id}") is True
