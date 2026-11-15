"""Project request and response schemas."""

import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from devflow_api.models.project import Project

type ProjectStatus = Literal["active", "archived", "completed"]


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    status: ProjectStatus = "active"
    tags: list[str] = Field(default_factory=list)


class ProjectResponse(ProjectCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def parse_tags(cls, data: object) -> object:
        if isinstance(data, Project):
            return {
                "id": data.id,
                "name": data.name,
                "description": data.description,
                "status": data.status,
                "tags": json.loads(data.tags_json),
                "created_at": data.created_at,
                "updated_at": data.updated_at,
            }
        return data


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    status: ProjectStatus | None = None
    tags: list[str] | None = None
