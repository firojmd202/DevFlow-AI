"""Stable errors for the Wave 2 specification pipeline."""

from devflow_core.exceptions import DevFlowError


class SpecificationError(DevFlowError):
    code = "SPECIFICATION_ERROR"


class SpecificationNotFoundError(SpecificationError):
    code = "SPEC_NOT_FOUND"


class InvalidSpecTransitionError(SpecificationError):
    code = "INVALID_SPEC_TRANSITION"


class ApprovedSpecificationError(InvalidSpecTransitionError):
    code = "SPEC_APPROVED_NO_OVERWRITE"


class SpecDigestMismatchError(SpecificationError):
    code = "SPEC_DIGEST_MISMATCH"


class AttemptConflictError(SpecificationError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class TaskNotCancellableError(SpecificationError):
    code = "TASK_NOT_CANCELLABLE"


class SpecificationCancelledError(SpecificationError):
    code = "PROVIDER_CANCELLED"


class MalformedSpecificationError(SpecificationError):
    code = "MALFORMED_OUTPUT"
