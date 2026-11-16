"""Shared asynchronous ORM repository."""

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.models.base import Base


class BaseRepository[ModelT: Base]:
    def __init__(self, model: type[ModelT], session: AsyncSession) -> None:
        self.model = model
        self.session = session

    async def _commit(self) -> None:
        try:
            await self.session.commit()
        except SQLAlchemyError:
            await self.session.rollback()
            raise

    async def get(self, id: int) -> ModelT | None:
        return await self.session.get(self.model, id)

    async def list(self, offset: int = 0, limit: int = 50) -> list[ModelT]:
        query = (
            select(self.model)
            .order_by(*self.model.__table__.primary_key)
            .offset(offset)
            .limit(limit)
        )
        return list((await self.session.scalars(query)).all())

    async def create(self, obj_in: dict[str, object], *, commit: bool = True) -> ModelT:
        row = self.model(**obj_in)
        self.session.add(row)
        if commit:
            await self._commit()
            await self.session.refresh(row)
        else:
            await self.session.flush()
        return row

    async def update(self, id: int, obj_in: dict[str, object]) -> ModelT | None:
        row = await self.get(id)
        if row is None:
            return None
        for field, value in obj_in.items():
            setattr(row, field, value)
        await self._commit()
        await self.session.refresh(row)
        return row

    async def delete(self, id: int) -> bool:
        row = await self.get(id)
        if row is None:
            return False
        await self.session.delete(row)
        await self._commit()
        return True
