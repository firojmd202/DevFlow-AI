"""Exceptions shared across DevFlow AI packages."""


class DevFlowError(Exception):
    """Base exception for application errors."""


class ConfigurationError(DevFlowError):
    """Configuration cannot be used by the application."""
