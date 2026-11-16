"""Integration adapter errors."""

from devflow_core.exceptions import DevFlowError


class AdapterNotFoundError(DevFlowError):
    """The requested adapter is unregistered."""


class MissingCredentialError(DevFlowError):
    """A live adapter lacks a required credential."""


class IntegrationExecutionError(DevFlowError):
    """An integration action failed."""

    def __init__(
        self, integration_name: str, action: str, status_code: int | None, message: str
    ) -> None:
        self.integration_name = integration_name
        self.action = action
        self.status_code = status_code
        self.message = message
        super().__init__(message)


class MCPServerNotFoundError(DevFlowError):
    """The requested MCP server is unregistered."""


class MCPPermissionError(DevFlowError):
    """The requested MCP action is forbidden."""


class MCPTimeoutError(DevFlowError):
    """The MCP request timed out."""


class MCPApprovalRequiredError(DevFlowError):
    """The MCP action requires approval."""


class MCPApprovalExpiredError(DevFlowError):
    """The MCP approval expired."""
