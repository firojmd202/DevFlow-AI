"""Offline Wave 5 API authorization and GitHub outcome regressions."""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import partial
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.adapters.live.github import GitHubAdapter
from devflow_api.models import (
    GitHubConfirmation,
    RepositoryConfig,
    Workflow,
    WorkflowAuditLog,
    WorkflowRun,
)
from devflow_api.repositories.approval import AuditLogRepository
from devflow_api.repositories.github_confirmation import GitHubConfirmationRepository
from devflow_api.repositories.repository_config import RepositoryConfigRepository
from devflow_api.services.repository import (
    RepositoryService,
    canonical_branch_create_payload,
    canonical_pr_create_payload,
    hash_payload,
)
from devflow_core.config import Settings
from devflow_core.exceptions import ConfirmationMismatchError, ConfirmationRequiredError

REPOS = "/api/v1/repositories"
CONFIRM = "/api/v1/github-confirmations"
BRANCH = {"name": "Feature/test", "base_ref": "Main"}
PULL = {"title": "Example", "head": "Feature/test", "base": "Main", "body": "Body"}


@dataclass
class GitHubHarness:
    client: httpx.AsyncClient
    session: AsyncSession
    repo_id: int
    token: str
    status: int = 201
    timeout: bool = False
    writes: list[httpx.Request] = field(default_factory=list)

    def respond(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == f"token {self.token}"
        if request.method == "GET":
            path = request.url.path
            if "/commits/" in path and path.endswith("/check-runs"):
                return httpx.Response(200, json={"check_runs": []})
            if "/commits/" in path:
                return httpx.Response(200, json={"sha": "abc"})
            if path.endswith("/branches"):
                return httpx.Response(200, json=[{"name": "Main", "commit": {"sha": "abc"}}])
            if "/branches/" in path and not path.endswith("/required_status_checks"):
                return httpx.Response(200, json={"name": "Feature/test", "commit": {"sha": "abc"}})
            if path.endswith("/required_status_checks"):
                return httpx.Response(404)
            if path.endswith("/pulls") or "/pulls/" in path:
                pull = {
                    "number": 1,
                    "title": "Example",
                    "state": "open",
                    "base": {"ref": "Main"},
                    "head": {"ref": "Feature/test"},
                }
                return httpx.Response(200, json=[pull] if path.endswith("/pulls") else pull)
            return httpx.Response(200, json={"full_name": "owner/repo"})

        self.writes.append(request)
        if self.timeout:
            raise httpx.ReadTimeout("private", request=request)
        if self.status != 201:
            return httpx.Response(self.status, json={"message": self.token})
        if request.url.path.endswith("/git/refs"):
            return httpx.Response(201, json={"object": {"sha": "abc"}})
        return httpx.Response(
            201,
            json={
                "number": 1,
                "title": "Example",
                "state": "open",
                "base": {"ref": "Main"},
                "head": {"ref": "Feature/test"},
            },
        )

    async def issue(self, *, pull: bool = False, **extra: object) -> str:
        body: dict[str, object] = {
            "repo_full_name": " OWNER/REPO ",
            "operation": "pr_create" if pull else "branch_create",
            "parameters": PULL if pull else BRANCH,
        }
        response = await self.client.post(CONFIRM, json=body | extra)
        assert response.status_code == 201, response.text
        value: str = response.json()["id"]
        return value

    async def write(
        self, id: str, *, pull: bool = False, repo_id: int | None = None, **fields: object
    ) -> httpx.Response:
        path = "pull-requests" if pull else "branches"
        payload: dict[str, object] = dict(PULL if pull else BRANCH)
        return await self.client.post(
            f"{REPOS}/{repo_id or self.repo_id}/{path}",
            json=payload | fields | {"confirmation_id": id},
        )

    async def record(self, id: str) -> GitHubConfirmation:
        result = await self.session.get(GitHubConfirmation, id, populate_existing=True)
        assert result is not None
        return result

    async def set_record(self, id: str, **fields: object) -> None:
        await self.session.execute(
            update(GitHubConfirmation).where(GitHubConfirmation.id == id).values(**fields)
        )
        await self.session.commit()

    async def audit(self) -> list[WorkflowAuditLog]:
        return list(
            (
                await self.session.scalars(select(WorkflowAuditLog).order_by(WorkflowAuditLog.id))
            ).all()
        )

    async def assert_mismatch(self, id: str, **fields: object) -> None:
        response = await self.write(id, pull=False, repo_id=None, **fields)
        assert response.status_code == 422 and response.json()["code"] == "CONFIRMATION_MISMATCH"
        assert (await self.record(id)).status == "ISSUED" and not self.writes


@pytest.fixture
async def github_api(
    test_client: httpx.AsyncClient,
    api_app: FastAPI,
    async_db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_secret: str,
) -> GitHubHarness:
    source = await test_client.post("/api/v1/projects", json={"name": "Example"})
    project_id = source.json()["id"]
    repo = await test_client.post(
        REPOS, json={"project_id": project_id, "owner": "Owner", "repo": "Repo"}
    )
    assert repo.status_code == 201, repo.text
    settings = Settings(GITHUB_TOKEN=SecretStr(synthetic_secret), LOCAL_OPERATOR_ID="trusted-local")
    api_app.state.settings = settings
    api_app.state.adapter_registry.register_live("github", GitHubAdapter(settings))
    harness = GitHubHarness(test_client, async_db_session, repo.json()["id"], synthetic_secret)
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        partial(httpx.AsyncClient, transport=httpx.MockTransport(harness.respond)),
    )
    return harness


async def test_create_branch_requires_confirmation(github_api: GitHubHarness) -> None:
    result = await github_api.client.post(
        f"{REPOS}/{github_api.repo_id}/branches", json=BRANCH | {"confirmed": False}
    )
    assert result.status_code == 422 and result.json()["code"] == "CONFIRMATION_REQUIRED"


async def test_create_pr_requires_confirmation(github_api: GitHubHarness) -> None:
    result = await github_api.client.post(f"{REPOS}/{github_api.repo_id}/pull-requests", json=PULL)
    assert result.status_code == 422 and result.json()["code"] == "CONFIRMATION_REQUIRED"


async def test_boolean_flag_alone_insufficient_for_github_action(github_api: GitHubHarness) -> None:
    result = await github_api.client.post(
        f"{REPOS}/{github_api.repo_id}/branches", json={"confirmed": True}
    )
    assert result.status_code == 422 and result.json()["code"] == "CONFIRMATION_REQUIRED"
    assert not github_api.writes


async def test_branch_creation_logs_audit_event(github_api: GitHubHarness) -> None:
    assert (await github_api.write(await github_api.issue())).status_code == 201
    rows = await github_api.audit()
    assert (rows[-1].event_type, rows[-1].actor) == ("branch_created", "user")
    assert json.loads(github_api.writes[0].content)["ref"] == "refs/heads/Feature/test"


async def test_pr_creation_logs_audit_event(github_api: GitHubHarness) -> None:
    assert (await github_api.write(await github_api.issue(pull=True), pull=True)).status_code == 201
    rows = await github_api.audit()
    assert (rows[-1].event_type, rows[-1].actor) == ("pr_created", "user")
    assert json.loads(github_api.writes[0].content)["head"] == "Feature/test"


async def test_github_confirmation_persisted_to_db(github_api: GitHubHarness) -> None:
    row = await github_api.record(await github_api.issue())
    assert row.status == "ISSUED" and row.used_at is None and row.repo_full_name == "owner/repo"
    assert row.expires_at - row.issued_at == timedelta(seconds=600)
    assert not github_api.writes


async def _expired(scope: GitHubHarness) -> None:
    id = await scope.issue()
    await scope.set_record(id, expires_at=datetime.now(UTC) - timedelta(seconds=1))
    result = await scope.write(id)
    assert result.status_code == 422 and result.json()["code"] == "CONFIRMATION_EXPIRED"
    assert not scope.writes


async def test_confirmation_expires_after_ttl(github_api: GitHubHarness) -> None:
    await _expired(github_api)


async def test_expired_github_confirmation_rejected(github_api: GitHubHarness) -> None:
    await _expired(github_api)


async def test_replay_rejected_after_use(github_api: GitHubHarness) -> None:
    id = await github_api.issue()
    assert (await github_api.write(id)).status_code == 201
    assert (await github_api.write(id)).status_code == 409
    assert len(github_api.writes) == 1


async def test_used_github_confirmation_rejected_on_replay(github_api: GitHubHarness) -> None:
    id = await github_api.issue()
    await github_api.set_record(id, status="USED", used_at=datetime.now(UTC))
    assert (await github_api.write(id)).status_code == 409
    assert not github_api.writes


async def test_parameter_mismatch_rejected(github_api: GitHubHarness) -> None:
    await github_api.assert_mismatch(await github_api.issue(), name="Something else")


async def test_mismatched_parameters_hash_rejected(github_api: GitHubHarness) -> None:
    id = await github_api.issue()
    await github_api.set_record(id, parameters_hash="0" * 64)
    await github_api.assert_mismatch(id)


async def test_mismatched_operation_rejected(github_api: GitHubHarness) -> None:
    response = await github_api.write(await github_api.issue(), pull=True)
    assert response.status_code == 422 and response.json()["code"] == "CONFIRMATION_MISMATCH"
    assert not github_api.writes


async def _wrong_repo(scope: GitHubHarness) -> None:
    project_id = (await scope.client.get(f"{REPOS}/{scope.repo_id}")).json()["project_id"]
    response = await scope.client.post(
        REPOS, json={"project_id": project_id, "owner": "owner", "repo": "other"}
    )
    result = await scope.write(await scope.issue(), repo_id=response.json()["id"])
    assert result.status_code == 422 and result.json()["code"] == "CONFIRMATION_MISMATCH"
    assert not scope.writes


async def test_mismatched_repo_rejected(github_api: GitHubHarness) -> None:
    await _wrong_repo(github_api)


async def test_mismatched_repo_rejected_canonical(github_api: GitHubHarness) -> None:
    await _wrong_repo(github_api)


async def _failed(scope: GitHubHarness, expected: str) -> str:
    id = await scope.issue()
    response = await scope.write(id)
    assert response.status_code == 502 and response.json()["code"] == "INTEGRATION_ERROR"
    assert ("Verify GitHub state" in response.json()["error"]) == (expected == "INDETERMINATE")
    assert scope.token not in response.text
    row = await scope.record(id)
    assert row.status == "USED" and row.used_at is not None
    event = (await scope.audit())[-1]
    assert event.event_type == "github_action_failed"
    assert json.loads(event.payload_json or "{}")["outcome"] == expected
    assert len(scope.writes) == 1
    return id


async def test_recovery_after_github_api_failure(github_api: GitHubHarness) -> None:
    github_api.status = 500
    id = await _failed(github_api, "INDETERMINATE")
    assert (await github_api.write(id)).status_code == 409


async def test_github_confirmation_not_restored_after_api_failure(
    github_api: GitHubHarness,
) -> None:
    github_api.status = 422
    await _failed(github_api, "FAILED")


@pytest.mark.parametrize("status", [500, 502, 503, 504])
async def test_http_5xx_treated_as_indeterminate(github_api: GitHubHarness, status: int) -> None:
    github_api.status = status
    await _failed(github_api, "INDETERMINATE")


async def test_http_4xx_treated_as_failed(github_api: GitHubHarness) -> None:
    github_api.status = 422
    await _failed(github_api, "FAILED")


async def test_timeout_treated_as_indeterminate(github_api: GitHubHarness) -> None:
    github_api.timeout = True
    await _failed(github_api, "INDETERMINATE")


async def test_indeterminate_outcome_does_not_restore_confirmation(
    github_api: GitHubHarness,
) -> None:
    github_api.timeout = True
    await _failed(github_api, "INDETERMINATE")


async def test_new_confirmation_required_after_indeterminate(github_api: GitHubHarness) -> None:
    github_api.status = 503
    id = await _failed(github_api, "INDETERMINATE")
    assert (await github_api.write(id)).status_code == 409
    assert len(github_api.writes) == 1


def test_reconciliation_documented_before_retry() -> None:
    assert "Verify GitHub state before retrying" in (RepositoryService.__doc__ or "")


def test_canonical_hash_deterministic() -> None:
    branch = canonical_branch_create_payload(" OWNER/REPO ", " Feature/x ", " Main ")
    assert (
        branch == '{"base_ref":"Main","branch_name":"Feature/x",'
        '"operation":"branch_create","repo_full_name":"owner/repo"}'
    )
    assert hash_payload(branch) == hash_payload(
        canonical_branch_create_payload("owner/repo", "Feature/x", "Main")
    )
    pull = canonical_pr_create_payload("OWNER/REPO", " Title ", None, "Feature/x", "Main")
    assert (
        pull == '{"base_ref":"Main","body":"","head_ref":"Feature/x",'
        '"operation":"pr_create","repo_full_name":"owner/repo","title":"Title"}'
    )


async def test_mismatched_base_ref_rejected(github_api: GitHubHarness) -> None:
    await github_api.assert_mismatch(await github_api.issue(), base_ref="main")


async def test_mismatched_pr_head_rejected(github_api: GitHubHarness) -> None:
    id = await github_api.issue(pull=True)
    response = await github_api.write(id, pull=True, head="Feature/other")
    assert response.status_code == 422 and response.json()["code"] == "CONFIRMATION_MISMATCH"
    assert not github_api.writes


async def test_canonical_hash_mismatch_rejected(github_api: GitHubHarness) -> None:
    id = await github_api.issue(pull=True)
    response = await github_api.write(id, pull=True, body="Modified")
    assert response.status_code == 422 and response.json()["code"] == "CONFIRMATION_MISMATCH"


async def test_repo_identity_from_server_config_not_client(github_api: GitHubHarness) -> None:
    row = await github_api.record(
        await github_api.issue(parameters=BRANCH | {"repo_config_id": github_api.repo_id})
    )
    assert row.repo_full_name == "owner/repo"
    assert row.parameters_hash == hash_payload(
        canonical_branch_create_payload(
            row.repo_full_name,
            **{
                "branch_name": BRANCH["name"],
                "base_ref": BRANCH["base_ref"],
            },
        )
    )


async def test_actor_id_from_settings_not_request_body(github_api: GitHubHarness) -> None:
    id = await github_api.issue(actor_id="spoofed", workflow_run_id=999)
    row = await github_api.record(id)
    assert row.actor_id == "trusted-local" and row.workflow_run_id is None
    assert (await github_api.write(id, actor_id="spoofed")).status_code == 201


async def test_actor_id_mismatch_rejected(github_api: GitHubHarness) -> None:
    id = await github_api.issue()
    await github_api.set_record(id, actor_id="another-operator")
    await github_api.assert_mismatch(id)


async def test_standalone_operation_allowed_without_workflow_context(
    github_api: GitHubHarness,
) -> None:
    id = await github_api.issue()
    assert (await github_api.record(id)).workflow_run_id is None
    assert (await github_api.write(id)).status_code == 201


async def test_workflow_run_mismatch_rejected(github_api: GitHubHarness) -> None:
    workflow = Workflow(name="Example")
    github_api.session.add(workflow)
    await github_api.session.flush()
    run = WorkflowRun(workflow_id=workflow.id)
    github_api.session.add(run)
    await github_api.session.commit()
    id = await github_api.issue()
    await github_api.set_record(id, workflow_run_id=run.id)
    await github_api.assert_mismatch(id, workflow_run_id=run.id)


async def test_github_token_not_in_audit_log(github_api: GitHubHarness) -> None:
    github_api.status = 500
    await _failed(github_api, "INDETERMINATE")
    assert all(github_api.token not in (row.payload_json or "") for row in await github_api.audit())


async def test_no_merge_endpoint_exists(test_client: httpx.AsyncClient) -> None:
    paths = (await test_client.get("/openapi.json")).json()["paths"]
    assert all("merge" not in path.split("/") for path in paths)


async def test_no_automatic_pr_merge(test_client: httpx.AsyncClient) -> None:
    assert (await test_client.post(f"{REPOS}/1/pull-requests/1/merge")).status_code == 404


async def test_repository_crud_and_github_reads(github_api: GitHubHarness) -> None:
    client = github_api.client
    path = f"{REPOS}/{github_api.repo_id}"
    repo = (await client.get(path)).json()
    assert (await client.get(REPOS, params={"project_id": repo["project_id"]})).json() == [repo]
    assert (await client.get(REPOS)).json() == [repo]
    assert (
        await client.post(
            REPOS, json={"project_id": repo["project_id"], "owner": "OWNER", "repo": "Repo"}
        )
    ).status_code == 409
    assert (await client.get(path + "/branches")).json()[0]["name"] == "Main"
    assert (await client.get(path + "/branches/Feature/test/status")).json()[
        "branch_name"
    ] == "Feature/test"
    assert (await client.get(path + "/branches/Feature/test/ci")).json() == []
    assert (await client.get(path + "/pull-requests")).json()[0]["number"] == 1
    assert (await client.get(path + "/pull-requests/1")).json()["title"] == "Example"
    assert (await client.delete(path)).status_code == 204
    assert (await client.get(path)).status_code == 404
    assert (await client.delete(path)).status_code == 404


@pytest.mark.parametrize(
    ("selector", "parameters", "expected"),
    [
        ("owner", BRANCH, 422),
        ("other/repo", BRANCH, 404),
        ("owner/repo", BRANCH | {"repo_config_id": "1"}, 422),
        ("owner/repo", {"name": "test"}, 422),
        ("owner/repo", BRANCH | {"base_ref": 1}, 422),
        ("owner/repo", BRANCH | {"repo_config_id": 999}, 404),
    ],
)
async def test_issuance_rejects_invalid_operation_inputs(
    github_api: GitHubHarness, selector: str, parameters: dict[str, object], expected: int
) -> None:
    response = await github_api.client.post(
        CONFIRM,
        json={
            "repo_full_name": selector,
            "operation": "branch_create",
            "parameters": parameters,
        },
    )
    assert response.status_code == expected
    assert not github_api.writes and not await github_api.audit()


async def test_issuance_rejects_unrelated_repo_config(github_api: GitHubHarness) -> None:
    client = github_api.client
    original = (await client.get(f"{REPOS}/{github_api.repo_id}")).json()
    other = await client.post(
        REPOS,
        json={
            "project_id": original["project_id"],
            "owner": "owner",
            "repo": "other",
        },
    )
    response = await client.post(
        CONFIRM,
        json={
            "repo_full_name": "owner/repo",
            "operation": "branch_create",
            "parameters": BRANCH | {"repo_config_id": other.json()["id"]},
        },
    )
    assert response.status_code == 422 and response.json()["code"] == "CONFIRMATION_MISMATCH"
    assert not github_api.writes


async def test_registration_requires_project_and_valid_coordinates(
    test_client: httpx.AsyncClient,
) -> None:
    body = {"project_id": 999, "owner": "octocat", "repo": "test"}
    assert (await test_client.post(REPOS, json=body)).status_code == 404
    assert (await test_client.post(REPOS, json=body | {"owner": "../x"})).status_code == 422


async def test_inactive_repository_cannot_issue_or_execute(github_api: GitHubHarness) -> None:
    branch = await github_api.issue()
    pull = await github_api.issue(pull=True)
    row = await github_api.session.get(RepositoryConfig, github_api.repo_id)
    assert row is not None
    row.is_active = False
    await github_api.session.commit()
    assert (await github_api.write(branch)).status_code == 404
    assert (await github_api.write(pull, pull=True)).status_code == 404
    response = await github_api.client.post(
        CONFIRM,
        json={
            "repo_full_name": "owner/repo",
            "operation": "branch_create",
            "parameters": BRANCH,
        },
    )
    assert response.status_code == 404 and not github_api.writes


async def test_forged_and_trigger_expired_confirmation_do_not_authorize(
    github_api: GitHubHarness,
) -> None:
    response = await github_api.write(str(uuid4()))
    assert response.status_code == 404 and response.json()["code"] == "CONFIRMATION_NOT_FOUND"
    id = await github_api.issue()
    await github_api.set_record(id, status="EXPIRED")
    response = await github_api.write(id)
    assert response.status_code == 422 and response.json()["code"] == "CONFIRMATION_EXPIRED"
    assert not github_api.writes


async def test_github_conflict_is_definitive_and_single_use(github_api: GitHubHarness) -> None:
    id = await github_api.issue()
    github_api.status = 409
    result = await github_api.write(id)
    assert result.status_code == 409 and result.json()["code"] == "CONFLICT"
    assert (await github_api.record(id)).status == "USED"
    assert len(github_api.writes) == 1


async def test_service_rejects_missing_confirmation_and_workflow_issuance(
    github_api: GitHubHarness,
) -> None:
    settings = Settings(GITHUB_TOKEN=SecretStr(github_api.token))
    session = github_api.session
    service = RepositoryService(
        RepositoryConfigRepository(session),
        AuditLogRepository(session),
        GitHubAdapter(settings),
        GitHubConfirmationRepository(session),
        settings,
    )
    with pytest.raises(ConfirmationMismatchError):
        await service.issue_confirmation(
            github_api.repo_id, "branch_create", dict(BRANCH), workflow_run_id=1
        )
    with pytest.raises(ConfirmationRequiredError):
        await service.create_branch(github_api.repo_id, "Feature/test", "Main", None)
    assert not github_api.writes


async def test_github_credentials_required_for_issuance(test_client: httpx.AsyncClient) -> None:
    project = (await test_client.post("/api/v1/projects", json={"name": "Example"})).json()
    repo = await test_client.post(
        REPOS,
        json={
            "project_id": project["id"],
            "owner": "owner",
            "repo": "repo",
        },
    )
    assert repo.status_code == 201
    response = await test_client.post(
        CONFIRM,
        json={
            "repo_full_name": "owner/repo",
            "operation": "branch_create",
            "parameters": BRANCH,
        },
    )
    assert response.status_code == 403 and response.json()["code"] == "MISSING_CREDENTIAL"
