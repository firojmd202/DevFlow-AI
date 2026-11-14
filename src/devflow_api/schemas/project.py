"""Phase 0 projects schemas."""

from typing import Literal

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    status: Literal["active", "archived", "completed"] = "active"


class ProjectResponse(ProjectCreate):
    id: int
