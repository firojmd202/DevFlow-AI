from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from devflow_api.schemas.approval import ApprovalResponse

type WorkflowStatus = Literal["draft", "active", "paused", "completed", "failed"]
type WorkflowName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class WorkflowCreate(BaseModel):
    name: WorkflowName
    description: str | None = None
    project_id: int | None = None
    status: WorkflowStatus = "draft"


class WorkflowUpdate(BaseModel):
    name: WorkflowName | None = None
    description: str | None = None
    project_id: int | None = None
    status: WorkflowStatus | None = None


class WorkflowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    project_id: int | None
    status: str
    created_at: datetime
    updated_at: datetime


class WorkflowRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workflow_id: int
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    approvals: list[ApprovalResponse] = Field(default_factory=list)
    pending_approvals: list[ApprovalResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class AuditLogEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workflow_run_id: int | None
    event_type: str
    actor: str
    payload_json: str | None
    created_at: datetime
