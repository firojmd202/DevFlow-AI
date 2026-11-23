"""HTTP contracts for specification management."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from devflow_api.schemas.approval import ApprovalDecision
from devflow_api.schemas.specification import ArtifactType, SpecificationRequestCreate


class SpecificationCreateBody(SpecificationRequestCreate):
    provider_id: Literal["ollama", "openai"] = "ollama"
    model_id: str | None = Field(default=None, min_length=1, max_length=256)
    supersedes_version_id: int | None = Field(default=None, gt=0)


class SpecificationRequestResponse(SpecificationRequestCreate):
    id: int
    status: str
    version: int
    content_hash: str
    provider_id: str | None
    model_id: str | None
    created_at: datetime
    updated_at: datetime


class SpecificationUpdateBody(SpecificationRequestCreate):
    expected_version: int = Field(gt=0)


class AttemptTrigger(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int | None = Field(default=None, gt=0)
    provider_id: Literal["ollama", "openai"] | None = None
    model_id: str | None = Field(default=None, min_length=1, max_length=256)


class TaskResponse(BaseModel):
    task_id: str
    status: str = "pending"
    poll_url: str


class StatusResponse(BaseModel):
    status: str
    error_code: str | None = None
    error_message: str | None = None
    completed_at: datetime | None = None


class CancelTaskResponse(BaseModel):
    status: Literal["cancellation_requested"] = "cancellation_requested"


class VersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    version_number: int
    status: str
    content_digest: str | None
    supersedes_version_id: int | None
    created_at: datetime


class ArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    artifact_type: ArtifactType
    content: str
    content_hash: str


class FindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    severity: str
    dimension: str
    finding_text: str
    location: str
    recommendation: str
    source: str
    acknowledged: bool


class ReviewFindingsResponse(BaseModel):
    findings: list[FindingResponse]
    disclaimer: str
    summary: dict[str, int]


class ApprovalBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version_id: int = Field(gt=0)
    content_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class ApprovalBody(ApprovalBinding):
    approval_id: int = Field(gt=0)
    decision: ApprovalDecision
    reason: str | None = Field(default=None, max_length=1000)


class ApprovalResponse(BaseModel):
    id: int
    status: str
    expires_at: datetime | None = None
    version_id: int


class ProviderAvailability(BaseModel):
    provider_id: str
    model_id: str
    available: bool | None
    reason: str | None = None
