"""Local health endpoint."""

from fastapi import APIRouter, Request

from devflow_api.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> HealthResponse:
    return HealthResponse(version=request.app.version)
