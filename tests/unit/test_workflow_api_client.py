import json
from functools import partial

import httpx
import pytest

from devflow_ui.api_client import APIClient


async def test_workflow_and_approval_client_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "DELETE":
            return httpx.Response(204)
        if request.method == "GET" and request.url.path.rsplit("/", 1)[-1] in {
            "workflows",
            "runs",
            "audit",
            "approvals",
        }:
            return httpx.Response(200, json=[{"id": 1}])
        return httpx.Response(200, json={"id": 1})

    monkeypatch.setattr(
        httpx, "AsyncClient", partial(httpx.AsyncClient, transport=httpx.MockTransport(respond))
    )
    client = APIClient("http://test")
    assert await client.list_workflows(2, "active") == [{"id": 1}]
    assert await client.create_workflow("Workflow", 2) == {"id": 1}
    assert await client.get_workflow(1) == {"id": 1}
    assert await client.update_workflow(1, status="paused") == {"id": 1}
    assert await client.delete_workflow(1) is True
    assert await client.create_run(1) == {"id": 1}
    assert await client.list_runs(1) == [{"id": 1}]
    assert await client.get_run(1) == {"id": 1}
    assert await client.list_run_audit(1) == [{"id": 1}]
    assert await client.list_approvals() == [{"id": 1}]
    assert await client.get_approval(1) == {"id": 1}
    assert await client.resolve_approval(1, "approved", "reviewer") == {"id": 1}
    assert [(request.method, request.url.path.removeprefix("/api/v1")) for request in seen] == [
        ("GET", "/workflows"),
        ("POST", "/workflows"),
        ("GET", "/workflows/1"),
        ("PUT", "/workflows/1"),
        ("DELETE", "/workflows/1"),
        ("POST", "/workflows/1/runs"),
        ("GET", "/workflows/1/runs"),
        ("GET", "/workflow-runs/1"),
        ("GET", "/workflow-runs/1/audit"),
        ("GET", "/approvals"),
        ("GET", "/approvals/1"),
        ("POST", "/approvals/1/resolve"),
    ]
    assert dict(seen[0].url.params) == {"project_id": "2", "status": "active"}
    assert dict(seen[9].url.params) == {"status": "pending"}
    assert json.loads(seen[11].content) == {"decision": "approved", "resolved_by": "reviewer"}


@pytest.mark.parametrize("payload", [b"null", b'"invalid"', b"", b"{}"])
async def test_workflow_client_invalid_list(
    monkeypatch: pytest.MonkeyPatch, payload: bytes, caplog: pytest.LogCaptureFixture
) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=payload)

    monkeypatch.setattr(
        httpx, "AsyncClient", partial(httpx.AsyncClient, transport=httpx.MockTransport(respond))
    )
    assert await APIClient("http://test").list_workflows() is None
    assert caplog.records
