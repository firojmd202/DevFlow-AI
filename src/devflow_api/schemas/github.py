"""Typed GitHub transport results."""

from datetime import datetime
from typing import Literal

from pydantic import AliasPath, BaseModel, Field


class BranchSummary(BaseModel):
    name: str
    sha: str = Field(validation_alias=AliasPath("commit", "sha"))
    protected: bool = False


class BranchStatus(BaseModel):
    branch_name: str
    sha: str
    protected: bool
    ci_status: Literal["success", "failure", "pending", "unknown"]


class PullRequestSummary(BaseModel):
    number: int
    title: str
    state: str
    base_ref: str = Field(validation_alias=AliasPath("base", "ref"))
    head_ref: str = Field(validation_alias=AliasPath("head", "ref"))
    head_sha: str | None = Field(
        default=None, validation_alias=AliasPath("head", "sha"), exclude=True
    )
    merged_at: datetime | None = None
    checks_passed: bool = False


class CheckRunSummary(BaseModel):
    name: str
    status: Literal["queued", "in_progress", "completed"]
    conclusion: Literal["success", "failure", "skipped", "cancelled"] | None = None
    app_id: int | None = Field(default=None, validation_alias=AliasPath("app", "id"), exclude=True)


class RequiredCheck(BaseModel):
    context: str
    app_id: int | None = None


class RequiredChecks(BaseModel):
    contexts: list[str] = Field(default_factory=list)
    checks: list[RequiredCheck] = Field(default_factory=list)
