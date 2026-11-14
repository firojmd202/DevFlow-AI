"""Phase 0 learning schemas."""

from typing import Literal

from pydantic import BaseModel, Field


class LearningItemCreate(BaseModel):
    title: str = Field(min_length=1)
    source_url: str | None = None
    status: Literal["pending", "in_progress", "done"] = "pending"


class LearningItemResponse(LearningItemCreate):
    id: int
