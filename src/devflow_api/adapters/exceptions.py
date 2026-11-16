"""Integration adapter errors."""

from devflow_core.exceptions import DevFlowError


class AdapterNotFoundError(DevFlowError):
    """The requested adapter is unregistered."""


class MissingCredentialError(DevFlowError):
    """A live adapter lacks a required credential."""


class IntegrationExecutionError(DevFlowError):
    """An integration action failed."""

    def __init__(
        self,
        integration_name: str,
        action: str,
        status_code: int | None,
        message: str,
        *,
        response_body: str | None = None,
    ) -> None:
        self.integration_name = integration_name
        self.action = action
        self.status_code = status_code
        self.message = message
        self.response_body = response_body
        super().__init__(message)


class MCPServerNotFoundError(DevFlowError):
    """The requested MCP server is unregistered."""

    def __init__(self, server_name: str = "") -> None:
        self.server_name = server_name
        super().__init__("MCP server not found")


class MCPConnectionError(DevFlowError):
    """The MCP server could not be reached."""

    def __init__(self, server_name: str, cause: str = "Connection failed") -> None:
        self.server_name = server_name
        self.cause = cause
        super().__init__("MCP connection failed")


class MCPSecretResolutionError(DevFlowError):
    """An approved secret could not be resolved."""

    def __init__(self, key_name: str) -> None:
        self.key_name = key_name
        super().__init__("MCP secret could not be resolved")


class ConsumedError(DevFlowError):
    """An MCP approval could not be consumed."""

    def __init__(self, message: str, reason: str = "mismatched_binding") -> None:
        self.reason = reason
        super().__init__(message)


class MCPPermissionError(DevFlowError):
    """The requested MCP action is forbidden."""

    def __init__(self, server_name: str = "", tool_name: str = "") -> None:
        self.server_name = server_name
        self.tool_name = tool_name
        super().__init__("MCP permission denied")


class MCPTimeoutError(DevFlowError):
    """The MCP request timed out."""

    def __init__(
        self, server_name: str = "", tool_name: str = "", timeout_seconds: int = 0
    ) -> None:
        self.server_name = server_name
        self.tool_name = tool_name
        self.timeout_seconds = timeout_seconds
        super().__init__("MCP invocation timed out")


class MCPApprovalRequiredError(DevFlowError):
    """The MCP action requires approval."""

    def __init__(
        self, server_name: str = "", tool_name: str = "", classification: str = "unknown"
    ) -> None:
        self.server_name = server_name
        self.tool_name = tool_name
        self.classification = classification
        super().__init__("MCP approval required")


class MCPApprovalExpiredError(DevFlowError):
    """The MCP approval expired."""

    def __init__(self, server_name: str = "", tool_name: str = "") -> None:
        self.server_name = server_name
        self.tool_name = tool_name
        super().__init__("MCP approval expired")
