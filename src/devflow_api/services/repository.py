"""GitHub operations guarded by persisted, exact, single-use authorizations."""

import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

import httpx
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from devflow_api.adapters.exceptions import IntegrationExecutionError, MissingCredentialError
from devflow_api.adapters.live.github import GitHubAdapter
from devflow_api.adapters.stubs.github import GitHubStubAdapter
from devflow_api.models.github_confirmation import GitHubConfirmation
from devflow_api.models.project import Project
from devflow_api.models.repository import RepositoryConfig
from devflow_api.repositories.approval import AuditLogRepository
from devflow_api.repositories.github_confirmation import GitHubConfirmationRepository
from devflow_api.repositories.repository_config import RepositoryConfigRepository
from devflow_api.schemas.github import BranchSummary, PullRequestSummary
from devflow_api.schemas.repository import (
    BranchParameters,
    Operation,
    PullRequestParameters,
    RepositoryCreate,
)
from devflow_api.services._transaction import shared_session, transaction
from devflow_core.config import Settings
from devflow_core.exceptions import (
    ConfirmationAlreadyUsedError,
    ConfirmationExpiredError,
    ConfirmationMismatchError,
    ConfirmationNotFoundError,
    ConfirmationRequiredError,
)

_DEFINITIVE_REJECTIONS = frozenset({400, 401, 403, 404, 409, 422})


def canonical_branch_create_payload(repo_full_name: str, branch_name: str, base_ref: str) -> str:
    return json.dumps(
        {
            "operation": "branch_create",
            "repo_full_name": repo_full_name.strip().lower(),
            "branch_name": branch_name.strip(),
            "base_ref": base_ref.strip(),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def canonical_pr_create_payload(
    repo_full_name: str, title: str, body: str | None, head_ref: str, base_ref: str
) -> str:
    return json.dumps(
        {
            "operation": "pr_create",
            "repo_full_name": repo_full_name.strip().lower(),
            "title": title.strip(),
            "body": (body or "").strip(),
            "head_ref": head_ref.strip(),
            "base_ref": base_ref.strip(),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def hash_payload(payload: str) -> str:
    return sha256(payload.encode("utf-8")).hexdigest()


class GitHubOutcomeError(IntegrationExecutionError):
    def __init__(self, operation: str, outcome: str, status_code: int | None) -> None:
        self.outcome = outcome
        super().__init__("github", operation, status_code, "GitHub write failed")


class RepositoryService:
    """DevFlow AI cannot guarantee exactly-once execution. Verify GitHub state before retrying."""

    def __init__(
        self,
        repo_config_repo: RepositoryConfigRepository,
        audit_repo: AuditLogRepository,
        github_adapter: GitHubAdapter | GitHubStubAdapter,
        confirmation_repo: GitHubConfirmationRepository,
        settings: Settings,
    ) -> None:
        self.repositories = repo_config_repo
        self.audit = audit_repo
        self.confirmations = confirmation_repo
        self._github = github_adapter
        self._settings = settings
        self._session = shared_session(
            repo_config_repo.session, audit_repo.session, confirmation_repo.session
        )

    def github(self) -> GitHubAdapter:
        if not isinstance(self._github, GitHubAdapter) or not self._settings.GITHUB_TOKEN:
            raise MissingCredentialError("github", "GITHUB_TOKEN")
        return self._github

    async def get_repository(self, id: int) -> RepositoryConfig:
        repo = await self.repositories.get(id)
        if repo is None:
            raise HTTPException(404)
        return repo

    async def list_repositories(self, project_id: int | None) -> list[RepositoryConfig]:
        if project_id is not None:
            return await self.repositories.list_by_project(project_id)
        return list(
            await self._session.scalars(select(RepositoryConfig).order_by(RepositoryConfig.id))
        )

    async def register_repository(self, body: RepositoryCreate) -> RepositoryConfig:
        if await self._session.get(Project, body.project_id) is None:
            raise HTTPException(404)
        owner, repo = body.owner.lower(), body.repo.lower()
        if await self.repositories.get_by_coords(body.project_id, owner, repo) is not None:
            raise HTTPException(409)
        try:
            return await self.repositories.create(
                body.model_dump() | {"owner": owner, "repo": repo}
            )
        except IntegrityError:
            raise HTTPException(409) from None

    async def delete_repository(self, id: int) -> None:
        if not await self.repositories.delete(id):
            raise HTTPException(404)

    async def issue_for_coordinates(
        self,
        selector: str,
        operation: Operation,
        parameters: dict[str, object],
    ) -> GitHubConfirmation:
        owner, separator, repo = selector.lower().partition("/")
        if not separator or not owner or not repo or "/" in repo:
            raise HTTPException(422)
        config = await self.repositories.find_active(owner, repo)
        if config is None:
            raise HTTPException(404)
        supplied_id = parameters.get("repo_config_id", config.id)
        if type(supplied_id) is not int:
            raise HTTPException(422)
        selected = await self.get_repository(supplied_id)
        if selected.full_name != config.full_name:
            raise ConfirmationMismatchError()
        return await self.issue_confirmation(
            selected.id,
            operation,
            {key: value for key, value in parameters.items() if key != "repo_config_id"},
        )

    async def issue_confirmation(
        self,
        repo_config_id: int,
        operation: Operation,
        parameters: dict[str, object],
        workflow_run_id: int | None = None,
    ) -> GitHubConfirmation:
        if workflow_run_id is not None:
            raise ConfirmationMismatchError()
        config = await self.get_repository(repo_config_id)
        if not config.is_active:
            raise HTTPException(404)
        try:
            if operation == "branch_create":
                branch = BranchParameters.model_validate(parameters)
                payload = canonical_branch_create_payload(
                    config.full_name, branch.name, branch.base_ref
                )
            elif operation == "pr_create":
                pull = PullRequestParameters.model_validate(parameters)
                payload = canonical_pr_create_payload(
                    config.full_name, pull.title, pull.body, pull.head, pull.base
                )
            else:
                raise HTTPException(422)
        except ValidationError:
            raise HTTPException(422) from None
        await self.github().verify_repository_access(config.owner, config.repo)
        now = datetime.now(UTC)
        async with transaction(self._session):
            row = await self.confirmations.create(
                {
                    "id": str(uuid4()),
                    "repo_full_name": config.full_name,
                    "operation": operation,
                    "parameters_hash": hash_payload(payload),
                    "actor_id": self._settings.LOCAL_OPERATOR_ID,
                    "issued_at": now,
                    "expires_at": now
                    + timedelta(seconds=self._settings.GITHUB_CONFIRMATION_TTL_SECONDS),
                },
                commit=False,
            )
            await self._audit("github_confirmation_issued", config, operation, row.id, commit=False)
        return row

    async def _audit(
        self,
        event: str,
        config: RepositoryConfig,
        operation: Operation,
        confirmation_id: str | None,
        *,
        commit: bool = True,
        **extra: object,
    ) -> None:
        await self.audit.log_event(
            event,
            "user",
            None,
            {
                "repo_full_name": config.full_name,
                "operation": operation,
                "actor_id": self._settings.LOCAL_OPERATOR_ID,
                "confirmation_id": confirmation_id,
            }
            | extra,
            commit=commit,
        )

    async def _authorize(
        self,
        config: RepositoryConfig,
        operation: Operation,
        payload: str,
        confirmation_id: str | None,
    ) -> str:
        try:
            if not confirmation_id:
                raise ConfirmationRequiredError()
            row = await self.confirmations.get_by_id(confirmation_id)
            if row is None:
                raise ConfirmationNotFoundError()
            if row.status == "USED" or row.used_at is not None:
                raise ConfirmationAlreadyUsedError()
            now = datetime.now(UTC)
            if row.status == "EXPIRED" or row.expires_at <= now:
                raise ConfirmationExpiredError()
            bindings = (
                config.full_name,
                operation,
                hash_payload(payload),
                self._settings.LOCAL_OPERATOR_ID,
                None,
            )
            if (
                row.repo_full_name,
                row.operation,
                row.parameters_hash,
                row.actor_id,
                row.workflow_run_id,
            ) != bindings:
                raise ConfirmationMismatchError()
            await self.confirmations.consume_atomic(
                confirmation_id,
                now,
                repo_full_name=config.full_name,
                operation=operation,
                parameters_hash=bindings[2],
                actor_id=self._settings.LOCAL_OPERATOR_ID,
                workflow_run_id=None,
            )
        except (
            ConfirmationRequiredError,
            ConfirmationNotFoundError,
            ConfirmationAlreadyUsedError,
            ConfirmationExpiredError,
            ConfirmationMismatchError,
        ) as exc:
            await self._audit(
                "github_action_rejected", config, operation, None, reason=type(exc).__name__
            )
            raise
        await self._audit("github_action_authorized", config, operation, confirmation_id)
        return confirmation_id

    async def _execute[T](
        self,
        config: RepositoryConfig,
        operation: Operation,
        confirmation_id: str,
        call: Callable[[], Awaitable[T]],
        success_event: str,
    ) -> T:
        try:
            result = await call()
        except (
            IntegrationExecutionError,
            httpx.TransportError,
            TimeoutError,
            asyncio.CancelledError,
        ) as exc:
            status = exc.status_code if isinstance(exc, IntegrationExecutionError) else None
            outcome = "FAILED" if status in _DEFINITIVE_REJECTIONS else "INDETERMINATE"
            await self._audit(
                "github_action_failed", config, operation, confirmation_id, outcome=outcome
            )
            if isinstance(exc, asyncio.CancelledError):
                raise
            raise GitHubOutcomeError(operation, outcome, status) from None
        await self._audit(
            "github_action_executed", config, operation, confirmation_id, outcome="SUCCEEDED"
        )
        await self._audit(success_event, config, operation, confirmation_id)
        return result

    async def create_branch(
        self,
        repo_config_id: int,
        name: str,
        base_ref: str,
        confirmation_id: str | None,
    ) -> BranchSummary:
        config = await self.get_repository(repo_config_id)
        if not config.is_active:
            raise HTTPException(404)
        payload = canonical_branch_create_payload(config.full_name, name, base_ref)
        github = self.github()
        id = await self._authorize(config, "branch_create", payload, confirmation_id)

        async def create() -> BranchSummary:
            sha = await github.resolve_ref(config.owner, config.repo, base_ref.strip())
            return await github.create_branch(config.owner, config.repo, name.strip(), sha)

        return await self._execute(config, "branch_create", id, create, "branch_created")

    async def create_pull_request(
        self,
        repo_config_id: int,
        title: str,
        head: str,
        base: str,
        body: str | None,
        confirmation_id: str | None,
    ) -> PullRequestSummary:
        config = await self.get_repository(repo_config_id)
        if not config.is_active:
            raise HTTPException(404)
        payload = canonical_pr_create_payload(config.full_name, title, body, head, base)
        github = self.github()
        id = await self._authorize(config, "pr_create", payload, confirmation_id)

        async def create() -> PullRequestSummary:
            return await github.create_pull_request(
                config.owner,
                config.repo,
                title.strip(),
                head.strip(),
                base.strip(),
                (body or "").strip(),
            )

        return await self._execute(config, "pr_create", id, create, "pr_created")
