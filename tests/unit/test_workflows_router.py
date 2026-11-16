from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.models.approval import ApprovalRequest

WORKFLOWS = "/api/v1/workflows"
RUNS = "/api/v1/workflow-runs"


@pytest.fixture
async def workflow_run(test_client: httpx.AsyncClient) -> tuple[int, int]:
    workflow = await test_client.post(WORKFLOWS, json={"name": "Example"})
    assert workflow.status_code == 201
    workflow_id = int(workflow.json()["id"])
    response = await test_client.post(f"{WORKFLOWS}/{workflow_id}/runs")
    assert response.status_code == 201
    return workflow_id, int(response.json()["id"])


@pytest.fixture
async def run_approvals(
    workflow_run: tuple[int, int], async_db_session: AsyncSession
) -> list[ApprovalRequest]:
    _, run_id = workflow_run
    now = datetime.now(UTC)
    rows = [
        ApprovalRequest(
            workflow_run_id=run_id,
            step_name=status,
            action_description="Review",
            status=status,
            requested_at=timestamp,
            resolved_at=timestamp if status != "pending" else None,
            resolved_by="reviewer" if status in {"approved", "rejected"} else None,
        )
        for status, timestamp in [
            ("approved", now),
            ("pending", now),
            ("expired", now - timedelta(days=1)),
            ("rejected", now),
        ]
    ]
    async_db_session.add_all(rows)
    await async_db_session.commit()
    return rows


async def test_create_workflow_returns_201(test_client: httpx.AsyncClient) -> None:
    response = await test_client.post(WORKFLOWS, json={"name": "Example"})
    assert response.status_code == 201
    result = response.json()
    assert result["id"] > 0 and result["status"] == "draft"
    assert datetime.fromisoformat(result["created_at"]).utcoffset() == timedelta(0)
    assert "definition_json" not in result


async def test_list_workflows_filter_by_project_id(test_client: httpx.AsyncClient) -> None:
    project = await test_client.post("/api/v1/projects", json={"name": "Project"})
    project_id = project.json()["id"]
    expected = (
        await test_client.post(
            WORKFLOWS, json={"name": "Example", "project_id": project_id, "status": "active"}
        )
    ).json()
    await test_client.post(WORKFLOWS, json={"name": "Second", "status": "active"})
    await test_client.post(WORKFLOWS, json={"name": "Third", "project_id": project_id})
    filtered = await test_client.get(
        WORKFLOWS, params={"project_id": project_id, "status": "active"}
    )
    assert filtered.json() == [expected]
    assert len((await test_client.get(WORKFLOWS, params={"project_id": project_id})).json()) == 2
    assert len((await test_client.get(WORKFLOWS, params={"status": "active"})).json()) == 2


async def test_create_run_returns_pending_status(
    test_client: httpx.AsyncClient, workflow_run: tuple[int, int]
) -> None:
    workflow_id, run_id = workflow_run
    response = await test_client.get(f"{WORKFLOWS}/{workflow_id}/runs")
    assert response.status_code == 200
    assert [(item["id"], item["status"]) for item in response.json()] == [(run_id, "pending")]
    audit = await test_client.get(f"{RUNS}/{run_id}/audit")
    assert [(item["event_type"], item["actor"]) for item in audit.json()] == [
        ("run_created", "system")
    ]


async def test_workflow_run_response_includes_all_approvals(
    test_client: httpx.AsyncClient,
    workflow_run: tuple[int, int],
    run_approvals: list[ApprovalRequest],
) -> None:
    workflow_id, run_id = workflow_run
    audit_before = (await test_client.get(f"{RUNS}/{run_id}/audit")).json()
    response = await test_client.get(f"{RUNS}/{run_id}")
    assert response.status_code == 200
    records = response.json()["approvals"]
    expected = sorted(run_approvals, key=lambda row: (row.created_at, row.id))
    assert [(item["id"], item["status"], item["resolved_by"]) for item in records] == [
        (row.id, row.status, row.resolved_by) for row in expected
    ]
    assert (await test_client.get(f"{WORKFLOWS}/{workflow_id}/runs")).json() == [response.json()]
    assert (await test_client.get(f"{RUNS}/{run_id}/audit")).json() == audit_before


async def test_workflow_run_response_pending_approvals_filters_resolved(
    test_client: httpx.AsyncClient,
    workflow_run: tuple[int, int],
    run_approvals: list[ApprovalRequest],
) -> None:
    _, run_id = workflow_run
    result = (await test_client.get(f"{RUNS}/{run_id}")).json()
    assert len(result["approvals"]) == 4
    assert result["pending_approvals"] == [
        row for row in result["approvals"] if row["status"] == "pending"
    ]
    assert [row["id"] for row in result["pending_approvals"]] == [run_approvals[1].id]


async def test_workflow_run_response_empty_approvals_returns_empty_list(
    test_client: httpx.AsyncClient, workflow_run: tuple[int, int]
) -> None:
    _, run_id = workflow_run
    result = (await test_client.get(f"{RUNS}/{run_id}")).json()
    assert result["approvals"] == result["pending_approvals"] == []


async def test_update_delete_and_missing_workflow(
    test_client: httpx.AsyncClient, workflow_run: tuple[int, int]
) -> None:
    workflow_id, run_id = workflow_run
    path = f"{WORKFLOWS}/{workflow_id}"
    updated = await test_client.put(path, json={"name": "Changed", "status": "active"})
    assert updated.status_code == 200 and updated.json()["name"] == "Changed"
    assert (await test_client.get(path)).json() == updated.json()
    assert (await test_client.delete(path)).status_code == 204
    for url in [path, f"{path}/runs", f"{RUNS}/{run_id}", f"{RUNS}/{run_id}/audit"]:
        assert (await test_client.get(url)).status_code == 404
    assert (await test_client.post(f"{path}/runs")).status_code == 404
    assert (await test_client.put(path, json={})).status_code == 404
    assert (await test_client.delete(path)).status_code == 404


async def test_invalid_workflow_input(test_client: httpx.AsyncClient) -> None:
    for body in (
        {},
        {"name": " "},
        {"name": "Example", "project_id": 999},
        {"name": "X", "status": "running"},
    ):
        assert (await test_client.post(WORKFLOWS, json=body)).status_code == 422
    assert (await test_client.get(WORKFLOWS, params={"status": "pending"})).status_code == 422


async def test_invalid_status_transition_returns_422(test_client: httpx.AsyncClient) -> None:
    workflow = await test_client.post(WORKFLOWS, json={"name": "Paused", "status": "paused"})
    response = await test_client.post(f"{WORKFLOWS}/{workflow.json()['id']}/runs")
    assert response.status_code == 422 and response.json()["code"] == "INVALID_STATUS_TRANSITION"
