"""Kiro integration contract."""

from typing import Protocol

from devflow_api.adapters.protocols.base import BaseAdapterProtocol


class KiroAdapterProtocol(BaseAdapterProtocol, Protocol):
    def get_instructions(self, task: str) -> str: ...
