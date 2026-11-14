"""Stitch integration contract."""

from typing import Protocol

from devflow_api.adapters.protocols.base import BaseAdapterProtocol


class StitchAdapterProtocol(BaseAdapterProtocol, Protocol):
    """Health-only contract."""
