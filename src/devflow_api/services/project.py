"""Project creation, retrieval, updates and deletion."""

import json
from datetime import UTC, datetime

from fastapi import HTTPException

from devflow_api.repositories.project import ProjectRepository
from devflow_api.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate


class ProjectService:
    def __init__(self, repo: ProjectRepository) -> None:
        self.repo = repo

    async def list(
        self, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[ProjectResponse]:
        return [
            ProjectResponse.model_validate(row)
            for row in await self.repo.list_filtered(status, limit, offset)
        ]

    async def create(self, body: ProjectCreate) -> ProjectResponse:
        values = body.model_dump(exclude={"tags"})
        values["tags_json"] = json.dumps(body.tags)
        return ProjectResponse.model_validate(await self.repo.create(values))

    async def get(self, id: int) -> ProjectResponse:
        row = await self.repo.get(id)
        if row is None:
            raise HTTPException(status_code=404)
        return ProjectResponse.model_validate(row)

    async def update(self, id: int, body: ProjectUpdate) -> ProjectResponse:
        values = body.model_dump(exclude={"tags"}, exclude_none=True, exclude_unset=True)
        if body.tags is not None:
            values["tags_json"] = json.dumps(body.tags)
        values["updated_at"] = datetime.now(UTC)
        row = await self.repo.update(id, values)
        if row is None:
            raise HTTPException(status_code=404)
        return ProjectResponse.model_validate(row)

    async def delete(self, id: int) -> None:
        if not await self.repo.delete(id):
            raise HTTPException(status_code=404)
