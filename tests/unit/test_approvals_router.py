import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.adapters import exceptions as adapter_errors
from devflow_api.adapters.exceptions import IntegrationExecutionError, MissingCredentialError
from devflow_api.repositories.approval import ApprovalRepository, AuditLogRepository
from devflow_api.repositories.workflow import WorkflowRepository, WorkflowRunRepository
from devflow_api.services.approval import ApprovalService
from devflow_api.services.workflow import WorkflowService
from devflow_core import exceptions as core_errors
from devflow_core.exceptions import ConfirmationRequiredError

APPROVALS = "/api/v1/approvals"


@pytest.fixture
async def pending_approval(async_db_session: AsyncSession) -> tuple[int, int]:
    workflows = WorkflowRepository(async_db_session)
    runs = WorkflowRunRepository(async_db_session)
    audit = AuditLogRepository(async_db_session)
    workflow = await workflows.create({"name": "Review"})
    service = WorkflowService(workflows, runs, audit)
    run = await service.create_run(workflow.id)
    await service.transition_run(run.id, "running", "system")
    approval = await ApprovalService(
        ApprovalRepository(async_db_session), runs, audit
    ).request_approval(run.id, "review", "Review the request")
    return approval.id, run.id


@pytest.mark.parametrize(
    ("decision", "run_status"), [("approved", "running"), ("rejected", "cancelled")]
)
async def test_resolve_approval_approved_200(
    test_client: httpx.AsyncClient,
    pending_approval: tuple[int, int],
    decision: str,
    run_status: str,
) -> None:
    approval_id, run_id = pending_approval
    path = f"{APPROVALS}/{approval_id}"
    assert (await test_client.get(path)).json()["status"] == "pending"
    response = await test_client.post(
        f"{path}/resolve", json={"decision": decision, "resolved_by": "reviewer"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == decision
    assert response.json()["resolved_by"] == "reviewer" and response.json()["resolved_at"]
    run = (await test_client.get(f"/api/v1/workflow-runs/{run_id}")).json()
    assert run["status"] == run_status and run["approvals"] == [response.json()]
    assert run["pending_approvals"] == []
    assert (await test_client.get(APPROVALS, params={"status": "pending"})).json() == []
    assert (await test_client.get(APPROVALS)).json() == [response.json()]


async def test_resolve_approval_already_resolved_409(
    test_client: httpx.AsyncClient, pending_approval: tuple[int, int]
) -> None:
    approval_id, _ = pending_approval
    path = f"{APPROVALS}/{approval_id}/resolve"
    assert (await test_client.post(path, json={"decision": "approved"})).status_code == 200
    repeated = await test_client.post(path, json={"decision": "rejected"})
    assert repeated.status_code == 409 and repeated.json()["code"] == "APPROVAL_ALREADY_RESOLVED"


async def test_approval_filters_and_invalid_inputs(
    test_client: httpx.AsyncClient, pending_approval: tuple[int, int]
) -> None:
    approval_id, _ = pending_approval
    listing = await test_client.get(APPROVALS, params={"status": "pending"})
    assert [item["id"] for item in listing.json()] == [approval_id]
    assert (await test_client.get(APPROVALS, params={"status": "running"})).status_code == 422
    assert (await test_client.get(f"{APPROVALS}/999")).status_code == 404
    assert (
        await test_client.post(f"{APPROVALS}/999/resolve", json={"decision": "approved"})
    ).status_code == 404
    assert (
        await test_client.post(f"{APPROVALS}/{approval_id}/resolve", json={"decision": "expired"})
    ).status_code == 422


async def test_missing_credential_returns_403(
    api_app: FastAPI, test_client: httpx.AsyncClient
) -> None:
    @api_app.get("/missing-credential-probe")
    async def probe() -> None:
        raise MissingCredentialError("private credential value")

    response = await test_client.get("/missing-credential-probe")
    assert response.status_code == 403 and response.json()["code"] == "MISSING_CREDENTIAL"
    assert "private credential value" not in response.text


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (
            IntegrationExecutionError("adapter", "action", 500, "private details"),
            502,
            "INTEGRATION_ERROR",
        ),
        (ConfirmationRequiredError("private details"), 422, "CONFIRMATION_REQUIRED"),
        (core_errors.ConfirmationExpiredError(), 422, "CONFIRMATION_EXPIRED"),
        (core_errors.ConfirmationMismatchError(), 422, "CONFIRMATION_MISMATCH"),
        (core_errors.ConfirmationAlreadyUsedError(), 409, "CONFIRMATION_ALREADY_USED"),
        (core_errors.ConfirmationNotFoundError(), 404, "CONFIRMATION_NOT_FOUND"),
        (adapter_errors.MCPServerNotFoundError(), 404, "MCP_SERVER_NOT_FOUND"),
        (adapter_errors.MCPPermissionError(), 403, "MCP_PERMISSION_DENIED"),
        (adapter_errors.MCPTimeoutError(), 504, "MCP_TIMEOUT"),
        (adapter_errors.MCPApprovalRequiredError(), 403, "MCP_APPROVAL_REQUIRED"),
        (adapter_errors.MCPApprovalExpiredError(), 403, "MCP_APPROVAL_EXPIRED"),
    ],
)
async def test_safe_domain_error(
    api_app: FastAPI,
    test_client: httpx.AsyncClient,
    error: Exception,
    status: int,
    code: str,
) -> None:
    @api_app.get("/domain-error-probe")
    async def probe() -> None:
        raise error

    response = await test_client.get("/domain-error-probe")
    assert response.status_code == status and response.json()["code"] == code
    assert "private details" not in response.text
