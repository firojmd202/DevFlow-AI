"""Offline GitHub adapter."""

from devflow_api.adapters.capability import ExecutionMode, IntegrationCapability
from devflow_api.adapters.protocols.github import GitHubIssueResponse
from devflow_api.adapters.stubs._base import OfflineAdapter


class GitHubStubAdapter(OfflineAdapter):
    _capability = IntegrationCapability(
        name="github",
        execution_mode=ExecutionMode.AUTOMATED_API,
        supported_actions=["create_issue"],
        auth_required=True,
        auth_type="token",
        available_in_phase_0=False,
    )

    async def create_issue(self, repo: str, title: str, body: str) -> GitHubIssueResponse:
        return GitHubIssueResponse()
