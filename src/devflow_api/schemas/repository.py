"""HTTP schemas for repository registration and confirmation."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, StringConstraints, model_validator

from devflow_core.exceptions import ConfirmationRequiredError

type Nonempty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
type Coordinate = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^[a-zA-Z0-9_-][a-zA-Z0-9_.-]*$")
]
type Operation = Literal["branch_create", "pr_create"]


class RepositoryCreate(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    project_id: int = Field(gt=0)
    owner: Coordinate
    repo: Coordinate
    default_branch: Nonempty = "main"
    is_active: bool = True


class RepositoryConfigResponse(RepositoryCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class BranchParameters(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    name: Nonempty = Field(validation_alias=AliasChoices("name", "branch_name"))
    base_ref: Nonempty


class PullRequestParameters(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    title: Nonempty
    head: Nonempty = Field(validation_alias=AliasChoices("head", "head_ref"))
    base: Nonempty = Field(validation_alias=AliasChoices("base", "base_ref"))
    body: str | None = None


class BranchWrite(BranchParameters):
    model_config = ConfigDict(extra="ignore")
    confirmation_id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def require_confirmation(cls, value: object) -> object:
        return _require_confirmation(value)


class PullRequestWrite(PullRequestParameters):
    model_config = ConfigDict(extra="ignore")
    confirmation_id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def require_confirmation(cls, value: object) -> object:
        return _require_confirmation(value)


def _require_confirmation(value: object) -> object:
    if isinstance(value, dict) and not value.get("confirmation_id"):
        raise ConfirmationRequiredError()
    return value


class GitHubConfirmationRequest(BaseModel):
    # Client-supplied identity and workflow context are never consumed.
    model_config = ConfigDict(strict=True, extra="ignore")

    repo_full_name: Nonempty
    operation: Operation
    parameters: dict[str, object]


class GitHubConfirmationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    expires_at: datetime
