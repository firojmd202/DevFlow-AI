"""Project repository queries."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.models.repository import RepositoryConfig
from devflow_api.repositories.base import BaseRepository


class RepositoryConfigRepository(BaseRepository[RepositoryConfig]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(RepositoryConfig, session)

    async def list_by_project(self, project_id: int) -> list[RepositoryConfig]:
        query = select(RepositoryConfig).where(RepositoryConfig.project_id == project_id)
        return list((await self.session.scalars(query.order_by(RepositoryConfig.id))).all())

    async def get_by_coords(
        self, project_id: int, owner: str, repo: str
    ) -> RepositoryConfig | None:
        query = select(RepositoryConfig).where(
            RepositoryConfig.project_id == project_id,
            func.lower(RepositoryConfig.owner) == owner.lower(),
            func.lower(RepositoryConfig.repo) == repo.lower(),
        )
        return await self.session.scalar(query)

    async def find_active(self, owner: str, repo: str) -> RepositoryConfig | None:
        query = select(RepositoryConfig).where(
            func.lower(RepositoryConfig.owner) == owner.lower(),
            func.lower(RepositoryConfig.repo) == repo.lower(),
            RepositoryConfig.is_active.is_(True),
        )
        return await self.session.scalar(query.order_by(RepositoryConfig.id))
