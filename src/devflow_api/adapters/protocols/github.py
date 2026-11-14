"""GitHub integration contract."""

from typing import Protocol

from pydantic import BaseModel

from devflow_api.adapters.protocols.base import BaseAdapterProtocol


class GitHubIssueResponse(BaseModel):
    stub: bool = True


class GitHubAdapterProtocol(BaseAdapterProtocol, Protocol):
    async def create_issue(self, repo: str, title: str, body: str) -> GitHubIssueResponse: ...
