"""Integration metadata and health responses."""

from pydantic import BaseModel

from devflow_api.adapters.capability import IntegrationCapability


class IntegrationSummary(IntegrationCapability):
    """Capability metadata for an adapter."""


class IntegrationHealthResponse(BaseModel, extra="allow"):
    status: str
    integration: str
    execution_mode: str
