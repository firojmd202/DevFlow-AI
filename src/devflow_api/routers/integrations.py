"""Registry-backed integration metadata endpoints."""

from typing import cast

from fastapi import APIRouter, HTTPException, Request

from devflow_api.adapters.exceptions import AdapterNotFoundError
from devflow_api.adapters.registry import AdapterRegistry
from devflow_api.schemas.common import ErrorResponse
from devflow_api.schemas.integration import IntegrationHealthResponse, IntegrationSummary

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])


def _registry(request: Request) -> AdapterRegistry:
    return cast(AdapterRegistry, request.app.state.adapter_registry)


@router.get("")
async def list_integrations(request: Request) -> list[IntegrationSummary]:
    registry = _registry(request)
    return [
        IntegrationSummary.model_validate(
            registry.get_live(name).capability.model_dump()
            | {"mode": "stub" if registry.get_live(name) is registry.get(name) else "live"}
        )
        for name in registry.list_names()
    ]


@router.get("/{name}/health", responses={404: {"model": ErrorResponse}})
async def integration_health(name: str, request: Request) -> IntegrationHealthResponse:
    try:
        adapter = _registry(request).get_live(name)
    except AdapterNotFoundError as exc:
        raise HTTPException(status_code=404) from exc
    return IntegrationHealthResponse.model_validate(await adapter.health_check())
