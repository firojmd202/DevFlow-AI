"""Offline adapter registry for Phase 0."""

from devflow_api.adapters.exceptions import AdapterNotFoundError
from devflow_api.adapters.protocols.base import BaseAdapterProtocol
from devflow_api.adapters.stubs.antigravity import AntigravityStubAdapter
from devflow_api.adapters.stubs.chatgpt import ChatGPTStubAdapter
from devflow_api.adapters.stubs.claude import ClaudeStubAdapter
from devflow_api.adapters.stubs.codex import CodexStubAdapter
from devflow_api.adapters.stubs.figma import FigmaStubAdapter
from devflow_api.adapters.stubs.github import GitHubStubAdapter
from devflow_api.adapters.stubs.kiro import KiroStubAdapter
from devflow_api.adapters.stubs.mcp import MCPStubAdapter
from devflow_api.adapters.stubs.notebooklm import NotebookLMStubAdapter
from devflow_api.adapters.stubs.ollama import OllamaStubAdapter
from devflow_api.adapters.stubs.stitch import StitchStubAdapter


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, BaseAdapterProtocol] = {}
        self._live: dict[str, BaseAdapterProtocol] = {}

    def register(self, adapter: BaseAdapterProtocol) -> None:
        self._adapters[adapter.name] = adapter

    def get(self, name: str) -> BaseAdapterProtocol:
        try:
            return self._adapters[name]
        except KeyError as exc:
            raise AdapterNotFoundError(f"No adapter registered for '{name}'") from exc

    def list_names(self) -> list[str]:
        return sorted(self._adapters)

    def register_live(self, name: str, adapter: BaseAdapterProtocol) -> None:
        self.get(name)
        self._live[name] = adapter

    def get_live(self, name: str) -> BaseAdapterProtocol:
        stub = self.get(name)
        return self._live.get(name, stub)


registry = AdapterRegistry()
for adapter in (
    AntigravityStubAdapter(),
    ChatGPTStubAdapter(),
    ClaudeStubAdapter(),
    CodexStubAdapter(),
    FigmaStubAdapter(),
    GitHubStubAdapter(),
    KiroStubAdapter(),
    MCPStubAdapter(),
    NotebookLMStubAdapter(),
    OllamaStubAdapter(),
    StitchStubAdapter(),
):
    registry.register(adapter)
