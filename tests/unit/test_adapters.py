import ast
import os
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Never

import pytest
from pydantic import ValidationError

from devflow_api.adapters.capability import ExecutionMode, IntegrationCapability
from devflow_api.adapters.exceptions import AdapterNotFoundError
from devflow_api.adapters.protocols.base import BaseAdapterProtocol
from devflow_api.adapters.protocols.chatgpt import ChatGPTResponse
from devflow_api.adapters.protocols.claude import ClaudeResponse
from devflow_api.adapters.protocols.codex import CodexCLIRequest, CodexCLIResult
from devflow_api.adapters.protocols.figma import FigmaResponse
from devflow_api.adapters.protocols.github import GitHubIssueResponse
from devflow_api.adapters.protocols.mcp import MCPResponse
from devflow_api.adapters.protocols.ollama import OllamaResponse
from devflow_api.adapters.registry import registry
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
from tests.conftest import ROOT
from tests.unit.test_integrations_router import MODES

ADAPTERS = {
    "chatgpt": ChatGPTStubAdapter,
    "codex": CodexStubAdapter,
    "kiro": KiroStubAdapter,
    "claude": ClaudeStubAdapter,
    "antigravity": AntigravityStubAdapter,
    "stitch": StitchStubAdapter,
    "figma": FigmaStubAdapter,
    "notebooklm": NotebookLMStubAdapter,
    "github": GitHubStubAdapter,
    "ollama": OllamaStubAdapter,
    "mcp": MCPStubAdapter,
}


def test_capability_model() -> None:
    assert set(ExecutionMode) == {"automated_api", "cli_handoff", "manual_handoff", "unknown"}
    cli_mode: str = ExecutionMode.CLI_HANDOFF
    assert cli_mode == "cli_handoff"
    capability = ChatGPTStubAdapter().capability
    assert capability.supported_actions == ["complete"]
    assert capability.auth_required is True and capability.auth_type == "api_key"
    assert capability.available_in_phase_0 is False
    with pytest.raises(ValidationError):
        IntegrationCapability.model_validate(
            {**capability.model_dump(), "execution_mode": "invalid"}
        )


def test_registry() -> None:
    assert registry.list_names() == sorted(ADAPTERS)
    with pytest.raises(AdapterNotFoundError, match="nonexistent"):
        registry.get("nonexistent")


@pytest.mark.parametrize(("name", "mode"), MODES.items())
async def test_stub_health(name: str, mode: str) -> None:
    adapter = registry.get(name)
    assert isinstance(adapter, ADAPTERS[name])
    assert isinstance(adapter, BaseAdapterProtocol)
    assert adapter.capability.available_in_phase_0 is False
    assert await adapter.health_check() == {
        "status": "stub",
        "integration": name,
        "execution_mode": mode,
    }


async def test_codex_approval(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def deny(*args: object, **kwargs: object) -> Never:
        raise AssertionError("Codex must never launch a process")

    for owner, name in ((subprocess, "Popen"), (os, "system"), (os, "popen"), (os, "spawnv")):
        monkeypatch.setattr(owner, name, deny)
    adapter = CodexStubAdapter()
    request = adapter.request_code_generation("add tests", "python", str(tmp_path))
    assert isinstance(request, CodexCLIRequest)
    assert asdict(request) == {
        "description": "add tests",
        "language": "python",
        "workspace_path": str(tmp_path),
        "approved": False,
        "timeout_seconds": 30,
    }
    assert adapter.capability.execution_mode == "cli_handoff"
    assert adapter.capability.auth_type == "cli_auth"
    with pytest.raises(ValueError, match="explicitly approved"):
        await adapter.execute_approved_request(request)
    request.approved = True
    result = await adapter.execute_approved_request(request)
    assert isinstance(result, CodexCLIResult)
    assert result.stub and result.exit_code == 0 and not result.timed_out and result.stderr == ""
    assert "Phase 0" in result.stdout
    assert not list(tmp_path.iterdir())


def test_manual_and_unknown_actions() -> None:
    kiro, notebook = KiroStubAdapter(), NotebookLMStubAdapter()
    assert "Phase 0" in kiro.get_instructions(task="write tests")
    assert "Phase 0" in notebook.get_instructions(notebook_context="review notes")
    for adapter in (kiro, notebook, AntigravityStubAdapter(), StitchStubAdapter()):
        actions = {name for name in dir(adapter) if not name.startswith("_")}
        expected = {"name", "capability", "health_check"}
        if adapter.capability.execution_mode == "manual_handoff":
            expected.add("get_instructions")
        assert actions == expected


async def test_automated_actions_return_typed_placeholders() -> None:
    results = (
        (await ChatGPTStubAdapter().complete("prompt", "model"), ChatGPTResponse),
        (await ClaudeStubAdapter().complete("prompt", "model"), ClaudeResponse),
        (await FigmaStubAdapter().get_file("file"), FigmaResponse),
        (await GitHubStubAdapter().create_issue("repo", "title", "body"), GitHubIssueResponse),
        (await OllamaStubAdapter().generate("model", "prompt"), OllamaResponse),
        (await MCPStubAdapter().call_tool("server", "tool", {}), MCPResponse),
    )
    for result, response_type in results:
        assert isinstance(result, response_type) and result.stub is True


def test_offline_adapter_imports() -> None:
    banned = {"httpx", "requests", "subprocess", "socket", "urllib"}
    for path in (ROOT / "src/devflow_api/adapters/stubs").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                assert all(alias.name.split(".")[0] not in banned for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in banned
