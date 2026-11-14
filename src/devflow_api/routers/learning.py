"""Stateless Phase 0 learning endpoints."""

from typing import Never

from fastapi import APIRouter, HTTPException, Response

from devflow_api.schemas.common import ErrorResponse
from devflow_api.schemas.learning import LearningItemCreate, LearningItemResponse

router = APIRouter(prefix="/api/v1/learning", tags=["learning"])
_NOT_FOUND: dict[int | str, dict[str, object]] = {404: {"model": ErrorResponse}}
_VALIDATION: dict[int | str, dict[str, object]] = {422: {"model": ErrorResponse}}


@router.get("")
async def list_items() -> list[LearningItemResponse]:
    return []


@router.post("", responses=_VALIDATION)
async def create_item(body: LearningItemCreate) -> LearningItemResponse:
    return LearningItemResponse(
        id=1, title=body.title, source_url=body.source_url, status=body.status
    )


@router.get("/{id}", response_model=LearningItemResponse, responses={**_NOT_FOUND, **_VALIDATION})
async def get_item(id: int) -> Never:
    raise HTTPException(status_code=404)


@router.put("/{id}", response_model=LearningItemResponse, responses={**_NOT_FOUND, **_VALIDATION})
async def update_item(id: int, body: LearningItemCreate) -> Never:
    raise HTTPException(status_code=404)


@router.delete(
    "/{id}",
    status_code=204,
    response_class=Response,
    response_model=None,
    responses={**_NOT_FOUND, **_VALIDATION},
)
async def delete_item(id: int) -> Never:
    raise HTTPException(status_code=404)
