"""Exceptions shared across DevFlow AI packages."""


class DevFlowError(Exception):
    """Base exception for application errors."""


class ConfigurationError(DevFlowError):
    """Configuration cannot be used by the application."""


class InvalidStatusTransitionError(DevFlowError):
    def __init__(self, run_id: int, from_status: str, to_status: str) -> None:
        self.run_id = run_id
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(f"Run {run_id} cannot transition from {from_status} to {to_status}")


class ApprovalAlreadyResolvedError(DevFlowError):
    def __init__(self, approval_id: int, current_status: str) -> None:
        self.approval_id = approval_id
        self.current_status = current_status
        super().__init__(f"Approval {approval_id} has status {current_status}")
