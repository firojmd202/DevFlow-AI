from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

type ApprovalStatus = Literal["pending", "approved", "rejected", "expired"]
type ApprovalDecision = Literal["approved", "rejected"]


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workflow_run_id: int
    step_name: str
    action_description: str
    status: str
    requested_at: datetime
    resolved_at: datetime | None
    resolved_by: str | None


class ResolveApprovalRequest(BaseModel):
    decision: ApprovalDecision
    resolved_by: str | None = None
