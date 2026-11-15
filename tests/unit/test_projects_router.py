import httpx
import pytest
from sqlalchemy.exc import SQLAlchemyError

from devflow_api.models.project import Project
from devflow_api.repositories.project import ProjectRepository
from devflow_api.schemas.project import ProjectResponse

PATH = "/api/v1/projects"


async def test_database_failure_returns_generic_error(
    test_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fail_create(self: ProjectRepository, obj_in: dict[str, object]) -> Project:
        raise SQLAlchemyError("sensitive database detail")

    monkeypatch.setattr(ProjectRepository, "create", fail_create)
    response = await test_client.post(PATH, json={"name": "Example"})
    assert response.status_code == 500
    assert response.json() == {"error": "Internal server error", "code": "INTERNAL_ERROR"}


async def test_create_project_persists(test_client: httpx.AsyncClient) -> None:
    ids = []
    for value in ("First", "First"):
        response = await test_client.post(PATH, json={"name": value})
        assert response.status_code == 201
        record = ProjectResponse.model_validate(response.json())
        assert record.id > 0 and record.name == value
        assert record.created_at.utcoffset() is not None
        ids.append(record.id)
        assert (await test_client.get(f"{PATH}/{record.id}")).json() == response.json()
    listing = await test_client.get(PATH)
    assert listing.status_code == 200 and len(listing.json()) == 2 and len(set(ids)) == 2


async def test_missing_required_field(test_client: httpx.AsyncClient) -> None:
    response = await test_client.post(PATH, json={})
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
async def test_unknown_id(test_client: httpx.AsyncClient, method: str) -> None:
    response = await test_client.request(
        method, PATH + "/9999", json={"name": "Updated"} if method == "PUT" else None
    )
    assert response.status_code == 404
    assert response.json() == {"error": "Not found", "code": "NOT_FOUND"}


async def test_list_projects_filter_by_status(test_client: httpx.AsyncClient) -> None:
    assert (await test_client.get(PATH)).json() == []
    await test_client.post(PATH, json={"name": "First"})
    await test_client.post(PATH, json={"name": "Second", "status": "completed"})
    await test_client.post(PATH, json={"name": "Third"})
    filtered = await test_client.get(PATH, params={"status": "active"})
    assert [item["name"] for item in filtered.json()] == ["First", "Third"]
    page = await test_client.get(PATH, params={"limit": 1, "offset": 1})
    assert [item["name"] for item in page.json()] == ["Second"]
    for params in ({"status": "invalid"}, {"limit": "201"}, {"offset": "-1"}):
        assert (await test_client.get(PATH, params=params)).status_code == 422


async def test_update_project_partial(test_client: httpx.AsyncClient) -> None:
    created = (await test_client.post(PATH, json={"name": "First", "description": "Keep"})).json()
    url = f"{PATH}/{created['id']}"
    updated = await test_client.put(url, json={"name": "Second"})
    assert updated.status_code == 200
    data = updated.json()
    assert data["name"] == "Second" and data["description"] == "Keep"
    assert data["created_at"] == created["created_at"] and data["updated_at"] > data["created_at"]
    assert (await test_client.put(url, json={"status": "invalid"})).status_code == 422
    assert (await test_client.post(PATH, json={"name": ""})).status_code == 422


async def test_update_project_null_field_does_not_clear(test_client: httpx.AsyncClient) -> None:
    created = (await test_client.post(PATH, json={"name": "First", "description": "Keep"})).json()
    updated = await test_client.put(f"{PATH}/{created['id']}", json={"description": None})
    assert updated.status_code == 200 and updated.json()["description"] == "Keep"


async def test_delete_project_removes_record(test_client: httpx.AsyncClient) -> None:
    created = (await test_client.post(PATH, json={"name": "First"})).json()
    url = f"{PATH}/{created['id']}"
    deleted = await test_client.delete(url)
    assert deleted.status_code == 204 and not deleted.content
    assert (await test_client.get(url)).status_code == 404
