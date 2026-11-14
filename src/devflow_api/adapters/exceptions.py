"""Integration adapter errors."""

from devflow_core.exceptions import DevFlowError


class AdapterNotFoundError(DevFlowError):
    """The requested adapter is unregistered."""


class MissingCredentialError(DevFlowError):
    """A live adapter lacks a required credential."""
