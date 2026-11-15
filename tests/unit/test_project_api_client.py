from functools import partial

import httpx
import pytest

from devflow_ui.api_client import APIClient


async def test_project_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "GET":
            return httpx.Response(200, json=[{"id": 1}])
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(200, json={"id": 1})

    monkeypatch.setattr(
        httpx, "AsyncClient", partial(httpx.AsyncClient, transport=httpx.MockTransport(respond))
    )
    client = APIClient("http://test")
    assert await client.list_projects("active", 3, 2) == [{"id": 1}]
    assert dict(seen[0].url.params) == {"status": "active", "limit": "3", "offset": "2"}
    assert await client.create_project("Demo", tags=["test"]) == {"id": 1}
    assert await client.update_project(1, name="New") == {"id": 1}
    assert await client.delete_project(1)
    assert [request.method for request in seen] == ["GET", "POST", "PUT", "DELETE"]


@pytest.mark.parametrize("failure", ["connection", "http", "invalid-json", "invalid-shape"])
async def test_project_requests_fail_safely(monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if failure == "connection":
            raise httpx.ConnectError("unavailable", request=request)
        if failure == "http":
            return httpx.Response(503)
        if failure == "invalid-json":
            return httpx.Response(200, content=b"invalid")
        return httpx.Response(200, json=["unexpected"])

    monkeypatch.setattr(
        httpx, "AsyncClient", partial(httpx.AsyncClient, transport=httpx.MockTransport(respond))
    )
    client = APIClient("http://test")
    assert await client.list_projects() is None
    assert await client.create_project("Demo") is None
    assert await client.update_project(1, name="New") is None
    assert not await client.delete_project(1)


@pytest.mark.parametrize("payload", [{"status": "ok", "version": "0.1.0"}, [], {"status": 123}])
async def test_health_payload(monkeypatch: pytest.MonkeyPatch, payload: object) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/health"
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(
        httpx, "AsyncClient", partial(httpx.AsyncClient, transport=httpx.MockTransport(respond))
    )
    expected = payload if isinstance(payload, dict) and payload.get("status") == "ok" else None
    assert await APIClient("http://test").get_health() == expected
