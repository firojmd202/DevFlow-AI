import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr, ValidationError

from devflow_api.adapters.live.github import GitHubAdapter
from devflow_api.adapters.live.mcp_live import MCPLiveAdapter
from devflow_api.adapters.registry import registry
from devflow_api.main import create_app
from devflow_core.config import Settings
from tests.adapter_expectations import MODES


async def test_discovery(test_client: httpx.AsyncClient, api_app: FastAPI) -> None:
    assert api_app.state.adapter_registry.get("github") is registry.get("github")
    response = await test_client.get("/api/v1/integrations")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 11 and all(row["available_in_phase_0"] is False for row in rows)
    assert {row["name"]: row["execution_mode"] for row in rows} == MODES
    assert {row["name"] for row in rows if row["mode"] == "live"} == {"ollama"}


@pytest.mark.parametrize(("name", "mode"), MODES.items())
async def test_health(
    test_client: httpx.AsyncClient, name: str, mode: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import AsyncMock

    from devflow_api.adapters.live.ollama import OllamaAdapter

    status = "unavailable" if name == "ollama" else "stub"
    monkeypatch.setattr(
        OllamaAdapter,
        "health_check",
        AsyncMock(return_value={"status": status, "integration": name, "execution_mode": mode}),
    )
    response = await test_client.get(f"/api/v1/integrations/{name}/health")
    assert response.status_code == 200
    assert response.json() == {"status": status, "integration": name, "execution_mode": mode}


async def test_missing_adapter(test_client: httpx.AsyncClient) -> None:
    response = await test_client.get("/api/v1/integrations/nonexistent/health")
    assert response.status_code == 404
    assert response.json() == {"error": "Not found", "code": "NOT_FOUND"}


def test_mcp_config_validation_and_registry_isolation() -> None:
    for raw in (
        "[invalid json",
        '[{"name":"x","command":[]}]',
        '[{"name":"x","command":["a"]},{"name":"x","command":["b"]}]',
    ):
        with pytest.raises(ValidationError, match="Invalid MCP server configuration"):
            Settings(MCP_SERVERS_CONFIG=raw)
    configured = create_app(
        Settings(
            GITHUB_TOKEN=SecretStr("synthetic"),
            FIGMA_TOKEN=SecretStr("synthetic"),
            MCP_SERVERS_CONFIG='[{"name":"x","command":["example"]}]',
        )
    ).state.adapter_registry
    disabled = create_app(
        Settings(
            GITHUB_TOKEN=None,
            MCP_SERVERS_CONFIG='[{"name":"x","command":["example"],"enabled":false}]',
        )
    ).state.adapter_registry
    assert isinstance(configured.get_live("github"), GitHubAdapter)
    assert isinstance(configured.get_live("mcp"), MCPLiveAdapter)
    assert disabled.get_live("github") is disabled.get("github")
    assert disabled.get_live("mcp") is disabled.get("mcp")
