"""Live GitHub issue adapter."""

from typing import Literal
from urllib.parse import quote

from pydantic import TypeAdapter, ValidationError

from devflow_api.adapters.capability import IntegrationCapability
from devflow_api.adapters.exceptions import IntegrationExecutionError, MissingCredentialError
from devflow_api.adapters.live._http import LiveHTTPAdapter
from devflow_api.adapters.protocols.github import GitHubIssueResponse
from devflow_api.schemas.github import (
    BranchStatus,
    BranchSummary,
    CheckRunSummary,
    PullRequestSummary,
    RequiredCheck,
    RequiredChecks,
)
from devflow_core.config import Settings


class GitHubAdapter(LiveHTTPAdapter):
    def __init__(self, settings: Settings) -> None:
        super().__init__(
            "github",
            "create_issue",
            settings.GITHUB_API_BASE_URL,
            10.0,
            credential_key="GITHUB_TOKEN",
        )
        self._token = settings.GITHUB_TOKEN

    @property
    def capability(self) -> IntegrationCapability:
        return super().capability.model_copy(
            update={
                "supported_actions": [
                    "create_issue",
                    "list_branches",
                    "get_branch_status",
                    "list_pull_requests",
                    "get_pull_request",
                    "create_branch",
                    "create_pull_request",
                    "get_check_runs",
                ]
            }
        )

    def _headers(self) -> dict[str, str]:
        if not self._token:
            raise MissingCredentialError("github", "GITHUB_TOKEN")
        return {
            "Authorization": f"token {self._token.get_secret_value()}",
            "Accept": "application/vnd.github+json",
        }

    async def create_issue(self, repo: str, title: str, body: str) -> GitHubIssueResponse:
        self._headers()
        parts = repo.split("/")
        if len(parts) != 2 or any(part in {"", ".", ".."} for part in parts):
            raise ValueError("GitHub repository must be owner/name")
        owner, name = (quote(part, safe="") for part in parts)
        await self._request(
            "create_issue",
            "POST",
            f"/repos/{owner}/{name}/issues",
            payload={"title": title, "body": body},
            preserve_error_body=True,
        )
        return GitHubIssueResponse(stub=False)

    async def health_check(self) -> dict[str, str]:
        return await self._health("/user")

    async def verify_repository_access(self, owner: str, repo: str) -> None:
        await self._request("verify_repository_access", "GET", self._repo_path(owner, repo))

    async def resolve_ref(self, owner: str, repo: str, ref: str) -> str:
        result = await self._json(
            "resolve_ref",
            f"{self._repo_path(owner, repo)}/commits/{quote(ref, safe='')}",
            TypeAdapter(dict[str, object]),
        )
        sha = result.get("sha")
        if not isinstance(sha, str) or not sha:
            raise IntegrationExecutionError("github", "resolve_ref", None, "Invalid GitHub commit")
        return sha

    def _repo_path(self, owner: str, repo: str) -> str:
        self._headers()
        if any(part in {"", ".", ".."} for part in (owner, repo)):
            raise ValueError("GitHub repository must be owner/name")
        return f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}"

    async def _json[T](
        self,
        action: str,
        path: str,
        schema: TypeAdapter[T],
        payload: dict[str, object] | None = None,
    ) -> T:
        response = await self._request(
            action,
            "POST" if payload is not None else "GET",
            path,
            payload=payload,
            preserve_error_body=True,
        )
        try:
            return schema.validate_json(response.content)
        except ValidationError:
            raise IntegrationExecutionError(
                self.name, action, response.status_code, "GitHub returned an invalid response"
            ) from None

    async def list_branches(self, owner: str, repo: str) -> list[BranchSummary]:
        return await self._json(
            "list_branches",
            f"{self._repo_path(owner, repo)}/branches",
            TypeAdapter(list[BranchSummary]),
        )

    async def get_branch_status(self, owner: str, repo: str, branch: str) -> BranchStatus:
        item = await self._json(
            "get_branch_status",
            f"{self._repo_path(owner, repo)}/branches/{quote(branch, safe='')}",
            TypeAdapter(BranchSummary),
        )
        checks = await self.get_check_runs(owner, repo, item.sha)
        status: Literal["success", "failure", "pending", "unknown"] = "unknown"
        if any(check.conclusion in ("failure", "cancelled") for check in checks):
            status = "failure"
        elif any(check.status != "completed" for check in checks):
            status = "pending"
        elif checks and all(check.conclusion == "success" for check in checks):
            status = "success"
        return BranchStatus(
            branch_name=item.name, sha=item.sha, protected=item.protected, ci_status=status
        )

    async def list_pull_requests(self, owner: str, repo: str) -> list[PullRequestSummary]:
        pulls = await self._json(
            "list_pull_requests",
            f"{self._repo_path(owner, repo)}/pulls",
            TypeAdapter(list[PullRequestSummary]),
        )
        for pull in pulls:
            await self._check_pull(owner, repo, pull)
        return pulls

    async def get_pull_request(self, owner: str, repo: str, pr_number: int) -> PullRequestSummary:
        pull = await self._json(
            "get_pull_request",
            f"{self._repo_path(owner, repo)}/pulls/{pr_number}",
            TypeAdapter(PullRequestSummary),
        )
        return await self._check_pull(owner, repo, pull)

    async def _check_pull(
        self, owner: str, repo: str, pull: PullRequestSummary
    ) -> PullRequestSummary:
        if pull.head_sha is None:
            return pull
        base = quote(pull.base_ref, safe="")
        try:
            policy = await self._json(
                "required_checks",
                f"{self._repo_path(owner, repo)}/branches/{base}/protection/required_status_checks",
                TypeAdapter(RequiredChecks),
            )
        except IntegrationExecutionError as exc:
            if exc.status_code not in (403, 404):
                raise
            return pull
        required = policy.checks or [RequiredCheck(context=name) for name in policy.contexts]
        if required:
            checks = await self.get_check_runs(owner, repo, pull.head_sha)
            pull.checks_passed = all(
                any(
                    run.name == rule.context
                    and run.status == "completed"
                    and run.conclusion == "success"
                    and (rule.app_id in (None, -1) or run.app_id == rule.app_id)
                    for run in checks
                )
                for rule in required
            )
        return pull

    async def create_branch(self, owner: str, repo: str, name: str, base_sha: str) -> BranchSummary:
        result = await self._json(
            "create_branch",
            f"{self._repo_path(owner, repo)}/git/refs",
            TypeAdapter(dict[str, object]),
            {"ref": f"refs/heads/{name}", "sha": base_sha},
        )
        try:
            return BranchSummary.model_validate({"name": name, "commit": result["object"]})
        except (KeyError, ValidationError):
            raise IntegrationExecutionError(
                "github", "create_branch", 201, "Invalid GitHub branch"
            ) from None

    async def create_pull_request(
        self, owner: str, repo: str, title: str, head: str, base: str, body: str = ""
    ) -> PullRequestSummary:
        return await self._json(
            "create_pull_request",
            f"{self._repo_path(owner, repo)}/pulls",
            TypeAdapter(PullRequestSummary),
            {"title": title, "head": head, "base": base, "body": body},
        )

    async def get_check_runs(self, owner: str, repo: str, ref: str) -> list[CheckRunSummary]:
        result = await self._json(
            "get_check_runs",
            f"{self._repo_path(owner, repo)}/commits/{quote(ref, safe='')}/check-runs",
            TypeAdapter(dict[str, object]),
        )
        try:
            return TypeAdapter(list[CheckRunSummary]).validate_python(result.get("check_runs"))
        except ValidationError:
            raise IntegrationExecutionError(
                "github", "get_check_runs", 200, "Invalid GitHub checks"
            ) from None
