"""Offline tests for the live HTTP adapter contracts."""

import json
import logging
from collections.abc import Callable
from functools import partial

import httpx
import pytest
from pydantic import SecretStr

from devflow_api.adapters.exceptions import IntegrationExecutionError, MissingCredentialError
from devflow_api.adapters.live.figma import FigmaAdapter
from devflow_api.adapters.live.github import GitHubAdapter
from devflow_api.adapters.live.ollama import OllamaAdapter
from devflow_core.config import Settings


def mock_transport(
    monkeypatch: pytest.MonkeyPatch, respond: Callable[[httpx.Request], httpx.Response]
) -> None:
    monkeypatch.setattr(
        httpx, "AsyncClient", partial(httpx.AsyncClient, transport=httpx.MockTransport(respond))
    )


async def test_github_adapter_creates_issue(monkeypatch: pytest.MonkeyPatch) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == "https://api.github.com/repos/owner/repo/issues"
        assert request.headers["Authorization"] == "token synthetic"
        assert json.loads(request.content) == {"title": "Example", "body": "Details"}
        assert request.extensions["timeout"]["read"] == 10.0
        return httpx.Response(201, json={"number": 1})

    mock_transport(monkeypatch, respond)
    response = await GitHubAdapter(Settings(GITHUB_TOKEN=SecretStr("synthetic"))).create_issue(
        "owner/repo", "Example", "Details"
    )
    assert not response.stub


async def test_github_adapter_raises_missing_credential() -> None:
    with pytest.raises(MissingCredentialError):
        await GitHubAdapter(Settings(GITHUB_TOKEN=None)).create_issue("owner/repo", "x", "y")


async def test_github_adapter_timeout_raises_integration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("private transport detail", request=request)

    mock_transport(monkeypatch, respond)
    with pytest.raises(IntegrationExecutionError) as error:
        await GitHubAdapter(Settings(GITHUB_TOKEN=SecretStr("synthetic"))).create_issue(
            "owner/repo", "x", "y"
        )
    assert error.value.status_code is None
    assert "private transport detail" not in str(error.value)


async def test_github_token_not_in_log_records(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, synthetic_secret: str
) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == f"token {synthetic_secret}"
        return httpx.Response(403, text=synthetic_secret)

    mock_transport(monkeypatch, respond)
    with caplog.at_level(logging.INFO), pytest.raises(IntegrationExecutionError) as error:
        await GitHubAdapter(Settings(GITHUB_TOKEN=SecretStr(synthetic_secret))).create_issue(
            "owner/repo", "x", "y"
        )
    assert error.value.status_code == 403
    assert error.value.response_body == synthetic_secret
    assert synthetic_secret not in str(error.value)
    assert synthetic_secret not in caplog.text


async def test_ollama_adapter_generate(monkeypatch: pytest.MonkeyPatch) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == "http://localhost:11434/api/generate"
        assert request.extensions["timeout"]["read"] == 12.0
        assert json.loads(request.content) == {"model": "local", "prompt": "hello", "stream": False}
        return httpx.Response(200)

    mock_transport(monkeypatch, respond)
    response = await OllamaAdapter(Settings(OLLAMA_TIMEOUT_SECONDS=12)).generate("local", "hello")
    assert not response.stub


async def test_ollama_health_check_unavailable_when_not_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("unavailable", request=request)

    mock_transport(monkeypatch, respond)
    assert (await OllamaAdapter(Settings()).health_check())["status"] == "unavailable"


async def test_figma_adapter_raises_missing_credential() -> None:
    with pytest.raises(MissingCredentialError):
        await FigmaAdapter(Settings(FIGMA_TOKEN=None)).get_file("file")


@pytest.mark.parametrize("status_code", [200, 404])
async def test_figma_file_request(monkeypatch: pytest.MonkeyPatch, status_code: int) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == "https://api.figma.com/v1/files/file"
        assert request.headers["X-Figma-Token"] == "synthetic"
        assert request.extensions["timeout"]["read"] == 10.0
        return httpx.Response(status_code)

    mock_transport(monkeypatch, respond)
    adapter = FigmaAdapter(Settings(FIGMA_TOKEN=SecretStr("synthetic")))
    if status_code == 200:
        assert not (await adapter.get_file("file")).stub
    else:
        with pytest.raises(IntegrationExecutionError) as error:
            await adapter.get_file("file")
        assert error.value.status_code == 404


@pytest.mark.parametrize(
    ("checks", "expected"),
    [
        ([], "unknown"),
        ([{"name": "CI", "status": "completed", "conclusion": "success"}], "success"),
        ([{"name": "CI", "status": "completed", "conclusion": "failure"}], "failure"),
        ([{"name": "CI", "status": "in_progress"}], "pending"),
    ],
)
async def test_github_branch_and_ci(
    monkeypatch: pytest.MonkeyPatch, checks: list[dict[str, str]], expected: str
) -> None:
    branch = {"name": "main", "protected": True, "commit": {"sha": "abc"}}

    def respond(request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/repos/owner/repo")
        if path == "/branches":
            return httpx.Response(200, json=[branch])
        if path == "/branches/main":
            return httpx.Response(200, json=branch)
        assert path == "/commits/abc/check-runs"
        return httpx.Response(200, json={"check_runs": checks})

    mock_transport(monkeypatch, respond)
    adapter = GitHubAdapter(Settings(GITHUB_TOKEN=SecretStr("synthetic")))
    assert (await adapter.list_branches("owner", "repo"))[0].sha == "abc"
    status = await adapter.get_branch_status("owner", "repo", "main")
    assert status.protected and status.ci_status == expected
    assert adapter.capability.available_in_phase_0 is False


async def test_github_pull_and_create_ref_contracts(monkeypatch: pytest.MonkeyPatch) -> None:
    pull = {
        "number": 13,
        "title": "Example",
        "state": "open",
        "base": {"ref": "main"},
        "head": {"ref": "feature", "sha": "abc"},
    }

    def respond(request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/repos/owner/repo")
        if path == "/git/refs":
            assert request.method == "POST"
            assert json.loads(request.content) == {"ref": "refs/heads/feature", "sha": "abc"}
            return httpx.Response(201, json={"object": {"sha": "abc"}})
        if path == "/pulls" and request.method == "GET":
            return httpx.Response(200, json=[pull])
        if path == "/pulls/13":
            return httpx.Response(200, json=pull)
        if "/protection/required_status_checks" in path:
            return httpx.Response(404)
        assert path == "/pulls" and request.method == "POST"
        assert json.loads(request.content)["head"] == "feature"
        return httpx.Response(201, json=pull)

    mock_transport(monkeypatch, respond)
    adapter = GitHubAdapter(Settings(GITHUB_TOKEN=SecretStr("synthetic")))
    assert (await adapter.create_branch("owner", "repo", "feature", "abc")).name == "feature"
    assert (await adapter.list_pull_requests("owner", "repo"))[0].head_ref == "feature"
    assert not (await adapter.get_pull_request("owner", "repo", 13)).checks_passed
    assert (
        await adapter.create_pull_request("owner", "repo", "Example", "feature", "main")
    ).number == 13


@pytest.mark.parametrize(
    ("app_id", "conclusion", "passed"),
    [
        (2, "success", True),
        (3, "success", False),
        (2, "failure", False),
    ],
)
async def test_github_required_checks_must_match_source_and_pass(
    monkeypatch: pytest.MonkeyPatch, app_id: int, conclusion: str, passed: bool
) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/pulls/13"):
            return httpx.Response(
                200,
                json={
                    "number": 13,
                    "title": "Example",
                    "state": "open",
                    "base": {"ref": "main"},
                    "head": {"ref": "feature", "sha": "abc"},
                },
            )
        if path.endswith("/required_status_checks"):
            return httpx.Response(200, json={"checks": [{"context": "CI", "app_id": 2}]})
        assert path.endswith("/commits/abc/check-runs")
        return httpx.Response(
            200,
            json={
                "check_runs": [
                    {
                        "name": "CI",
                        "status": "completed",
                        "conclusion": conclusion,
                        "app": {"id": app_id},
                    }
                ]
            },
        )

    mock_transport(monkeypatch, respond)
    adapter = GitHubAdapter(Settings(GITHUB_TOKEN=SecretStr("synthetic")))
    assert (await adapter.get_pull_request("owner", "repo", 13)).checks_passed is passed
