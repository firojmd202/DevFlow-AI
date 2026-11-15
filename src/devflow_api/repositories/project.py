"""Project queries and tag storage."""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.models.project import Project
from devflow_api.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Project, session)

    async def list_filtered(
        self, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[Project]:
        query = select(Project).order_by(Project.id).offset(offset).limit(limit)
        if status is not None:
            query = query.where(Project.status == status)
        return list((await self.session.scalars(query)).all())

    async def update_tags(self, id: int, tags: list[str]) -> Project | None:
        return await self.update(id, {"tags_json": json.dumps(tags)})
