"""Register application models in the shared metadata."""

from devflow_api.models.approval import ApprovalRequest
from devflow_api.models.audit import WorkflowAuditLog
from devflow_api.models.base import Base
from devflow_api.models.integration import IntegrationConfig
from devflow_api.models.learning import LearningItem
from devflow_api.models.project import Project
from devflow_api.models.workflow import Workflow, WorkflowRun

__all__ = [
    "ApprovalRequest",
    "Base",
    "IntegrationConfig",
    "LearningItem",
    "Project",
    "Workflow",
    "WorkflowAuditLog",
    "WorkflowRun",
]
