"""Antigravity integration contract."""

from typing import Protocol

from devflow_api.adapters.protocols.base import BaseAdapterProtocol


class AntigravityAdapterProtocol(BaseAdapterProtocol, Protocol):
    """Health-only contract."""
