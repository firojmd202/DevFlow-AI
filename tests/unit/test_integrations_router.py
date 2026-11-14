import httpx
import pytest
from fastapi import FastAPI

from devflow_api.adapters.registry import registry
from tests.adapter_expectations import MODES


async def test_discovery(test_client: httpx.AsyncClient, api_app: FastAPI) -> None:
    assert api_app.state.adapter_registry is registry
    response = await test_client.get("/api/v1/integrations")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 11 and all(row["available_in_phase_0"] is False for row in rows)
    assert {row["name"]: row["execution_mode"] for row in rows} == MODES


@pytest.mark.parametrize(("name", "mode"), MODES.items())
async def test_health(test_client: httpx.AsyncClient, name: str, mode: str) -> None:
    response = await test_client.get(f"/api/v1/integrations/{name}/health")
    assert response.status_code == 200
    assert response.json() == {"status": "stub", "integration": name, "execution_mode": mode}


async def test_missing_adapter(test_client: httpx.AsyncClient) -> None:
    response = await test_client.get("/api/v1/integrations/nonexistent/health")
    assert response.status_code == 404
    assert response.json() == {"error": "Not found", "code": "NOT_FOUND"}
