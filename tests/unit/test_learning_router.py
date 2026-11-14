import httpx
import pytest

from devflow_api.schemas.learning import LearningItemResponse

PATH = "/api/v1/learning"


async def test_post_echo_is_stateless(test_client: httpx.AsyncClient) -> None:
    for value in ("First", "Second"):
        response = await test_client.post(PATH, json={"title": value})
        assert response.status_code == 200
        record = LearningItemResponse.model_validate(response.json())
        assert record.id == 1 and record.title == value
    listing = await test_client.get(PATH)
    assert listing.status_code == 200 and listing.json() == []
    assert (await test_client.get(PATH + "/1")).status_code == 404


async def test_missing_required_field(test_client: httpx.AsyncClient) -> None:
    response = await test_client.post(PATH, json={})
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
async def test_unknown_id(test_client: httpx.AsyncClient, method: str) -> None:
    response = await test_client.request(
        method, PATH + "/9999", json={"title": "Updated"} if method == "PUT" else None
    )
    assert response.status_code == 404
    assert response.json() == {"error": "Not found", "code": "NOT_FOUND"}
