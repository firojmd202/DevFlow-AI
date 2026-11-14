"""NotebookLM integration contract."""

from typing import Protocol

from devflow_api.adapters.protocols.base import BaseAdapterProtocol


class NotebookLMAdapterProtocol(BaseAdapterProtocol, Protocol):
    def get_instructions(self, notebook_context: str) -> str: ...
