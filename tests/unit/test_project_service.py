import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.repositories.project import ProjectRepository
from devflow_api.schemas.project import ProjectCreate, ProjectUpdate
from devflow_api.services.project import ProjectService


async def test_project_tags_serialisation(async_db_session: AsyncSession) -> None:
    repository = ProjectRepository(async_db_session)
    service = ProjectService(repository)
    created = await service.create(ProjectCreate(name="Demo", tags=["one", "東京"]))
    assert created.id > 0 and created.tags == ["one", "東京"]
    assert (await service.get(created.id)).model_dump(mode="json") == created.model_dump(
        mode="json"
    )
    row = await repository.update_tags(created.id, ["two"])
    assert row is not None and row.tags_json == '["two"]'
    assert (await service.update(created.id, ProjectUpdate(tags=[]))).tags == []
    assert (await repository.list())[0].id == created.id
    with pytest.raises(HTTPException) as exc:
        await service.get(9999)
    assert exc.value.status_code == 404


async def test_failed_insert_rolls_back_and_leaves_session_usable(
    async_db_session: AsyncSession,
) -> None:
    repository = ProjectRepository(async_db_session)
    with pytest.raises(IntegrityError):
        await repository.create({"name": None})

    service = ProjectService(repository)
    assert await service.list() == []
    created = await service.create(ProjectCreate(name="After rollback"))
    assert (await service.get(created.id)).name == "After rollback"
