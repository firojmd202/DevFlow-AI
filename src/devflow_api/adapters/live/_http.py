"""Shared HTTP behavior for live integration adapters."""

import httpx

from devflow_api.adapters.capability import ExecutionMode, IntegrationCapability
from devflow_api.adapters.exceptions import IntegrationExecutionError, MissingCredentialError


class LiveHTTPAdapter:
    def __init__(
        self,
        name: str,
        action: str,
        base_url: str,
        timeout: float,
        *,
        credential_key: str | None = None,
    ) -> None:
        self.name = name
        self._action = action
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._credential_key = credential_key

    @property
    def capability(self) -> IntegrationCapability:
        token_required = self._credential_key is not None
        return IntegrationCapability(
            name=self.name,
            execution_mode=ExecutionMode.AUTOMATED_API,
            supported_actions=[self._action],
            auth_required=token_required,
            auth_type="token" if token_required else None,
            available_in_phase_0=False,
        )

    def _headers(self) -> dict[str, str]:
        return {}

    async def _request(
        self,
        action: str,
        method: str,
        path: str,
        *,
        payload: dict[str, object] | None = None,
        preserve_error_body: bool = False,
    ) -> httpx.Response:
        headers = self._headers()
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, trust_env=False, follow_redirects=False
            ) as client:
                response = await client.request(
                    method, f"{self._base_url}{path}", headers=headers, json=payload
                )
                response.raise_for_status()
                return response
        except httpx.HTTPStatusError as exc:
            raise IntegrationExecutionError(
                self.name,
                action,
                exc.response.status_code,
                "Integration returned an unsuccessful HTTP status",
                response_body=exc.response.text if preserve_error_body else None,
            ) from None
        except (httpx.RequestError, httpx.InvalidURL, ValueError):
            raise IntegrationExecutionError(
                self.name, action, None, "Integration request could not be completed"
            ) from None

    async def _health(self, path: str) -> dict[str, str]:
        try:
            await self._request("health_check", "GET", path)
        except (IntegrationExecutionError, MissingCredentialError):
            status = "unavailable"
        else:
            status = "ok"
        return {
            "status": status,
            "integration": self.name,
            "execution_mode": ExecutionMode.AUTOMATED_API,
        }
