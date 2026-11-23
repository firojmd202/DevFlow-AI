"""Offline HTTP contract tests for the Wave 2 providers."""

import asyncio
import builtins
import json
from collections.abc import Awaitable, Callable
from typing import cast
from unittest.mock import AsyncMock, Mock, call

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from devflow_api.main import create_app
from devflow_api.providers import http as provider_http
from devflow_api.providers.exceptions import (
    ProviderAuthError,
    ProviderConfigurationError,
    ProviderError,
    ProviderMalformedResponseError,
    ProviderQuotaError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from devflow_api.providers.factory import ProviderFactory
from devflow_api.providers.openai_provider import OpenAIProvider
from devflow_api.schemas.ai_provider import GenerationOptions
from devflow_core.config import Settings

type MockHandler = Callable[[httpx.Request], httpx.Response | Awaitable[httpx.Response]]
type InstallTransport = Callable[[MockHandler], list[httpx.Request]]


@pytest.fixture
def install_transport(monkeypatch: pytest.MonkeyPatch) -> InstallTransport:
    async_client = httpx.AsyncClient

    def install(handler: MockHandler) -> list[httpx.Request]:
        requests: list[httpx.Request] = []

        async def intercept(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            result = handler(request)
            if isinstance(result, httpx.Response):
                return result
            return await result

        def make_client(**kwargs: object) -> httpx.AsyncClient:
            assert kwargs["trust_env"] is False
            return async_client(
                transport=httpx.MockTransport(intercept),
                timeout=kwargs["timeout"],  # type: ignore[arg-type]
                trust_env=False,
            )

        monkeypatch.setattr(httpx, "AsyncClient", make_client)
        return requests

    return install


def test_default_and_explicit_ollama_do_not_import_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    import_module = cast(Callable[..., object], builtins.__import__)

    def intercept(name: str, *args: object, **kwargs: object) -> object:
        assert name != "devflow_api.providers.openai_provider"
        return import_module(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", intercept)
    assert ProviderFactory.create(Settings(_env_file=None)).provider_id == "ollama"
    configured = Settings(AI_PROVIDER="ollama", OPENAI_API_KEY=SecretStr("mock-value"))
    assert ProviderFactory.create(configured).provider_id == "ollama"


@pytest.mark.parametrize("value", ["", "  "])
def test_openai_requires_a_key(value: str) -> None:
    settings = Settings(AI_PROVIDER="openai", OPENAI_API_KEY=SecretStr(value))
    with pytest.raises(ProviderConfigurationError, match="openai"):
        ProviderFactory.create(settings)
    with pytest.raises(ProviderConfigurationError, match="openai"):
        OpenAIProvider(settings)
    with pytest.raises(ProviderConfigurationError, match="openai"):
        OpenAIProvider(Settings(AI_PROVIDER="ollama", OPENAI_API_KEY=SecretStr("mock-value")))


def test_invalid_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "unexpected")
    with pytest.raises(ValidationError, match="AI_PROVIDER"):
        Settings()
    invalid_url = httpx.URL("http://localhost", username="mock-private")
    settings = Settings(AI_PROVIDER="ollama", OLLAMA_BASE_URL=str(invalid_url))
    with pytest.raises(ProviderConfigurationError) as error:
        ProviderFactory.create(settings)
    assert "mock-private" not in str(error.value)
    with pytest.raises(ProviderConfigurationError):
        ProviderFactory.create(Settings(AI_PROVIDER="ollama", OLLAMA_MODEL=" "))
    with pytest.raises(ProviderConfigurationError):
        ProviderFactory.create(Settings(AI_PROVIDER="ollama", OLLAMA_BASE_URL="https://openai.com"))


def test_app_initializes_provider_without_http(install_transport: InstallTransport) -> None:
    requests = install_transport(lambda _: httpx.Response(500))
    app = create_app(Settings(AI_PROVIDER="ollama"))
    assert app.state.ai_provider.provider_id == "ollama"
    with pytest.raises(ProviderConfigurationError):
        create_app(Settings(AI_PROVIDER="openai", OPENAI_API_KEY=None))
    assert not requests


async def test_ollama_generation_and_health(install_transport: InstallTransport) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200)
        return httpx.Response(
            200, json={"response": '{"ok":true}', "prompt_eval_count": 2, "eval_count": 3}
        )

    requests = install_transport(respond)
    settings = Settings(AI_PROVIDER="ollama", OPENAI_API_KEY=SecretStr("mock-value"))
    provider = ProviderFactory.create(settings)
    assert (await provider.check_availability()).available
    assert await provider.check_capability("structured_output")
    assert not await provider.check_capability("tool_execution")
    result = await provider.generate(
        "Return JSON", GenerationOptions(json_output=True, max_tokens=5000), model="explicit"
    )
    assert result.model == "explicit" and result.content == '{"ok":true}'
    assert result.usage is not None
    assert result.usage.model_dump() == {
        "prompt_tokens": 2,
        "completion_tokens": 3,
        "total_tokens": 5,
    }
    assert [request.url.path for request in requests] == ["/api/tags", "/api/generate"]
    assert all(request.url.host == "localhost" for request in requests)
    assert all("Authorization" not in request.headers for request in requests)
    payload = json.loads(requests[1].content)
    assert payload["format"] == "json"
    assert payload["options"]["num_predict"] == settings.AI_MAX_OUTPUT_TOKENS
    assert requests[1].extensions["timeout"]["connect"] == settings.OLLAMA_TIMEOUT_SECONDS
    assert requests[1].extensions["timeout"]["read"] == settings.AI_REQUEST_TIMEOUT_SECONDS


async def test_openai_generation(install_transport: InstallTransport) -> None:
    requests = install_transport(
        lambda _: httpx.Response(
            200,
            headers={"x-request-id": "test-id"},
            json={
                "choices": [{"message": {"content": '{"ok":true}'}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
            },
        )
    )
    key = SecretStr("mock-value")
    assert str(key) == "**********"
    provider = ProviderFactory.create(Settings(AI_PROVIDER="openai", OPENAI_API_KEY=key))
    result = await provider.generate("Return JSON", GenerationOptions(json_output=True))
    assert result.provider_id == "openai" and result.finish_reason == "stop"
    assert result.request_id == "test-id"
    assert result.usage is not None and result.usage.total_tokens == 7
    assert requests[0].url.path == "/v1/chat/completions"
    assert requests[0].headers["Authorization"] == f"Bearer {key.get_secret_value()}"
    assert json.loads(requests[0].content)["response_format"] == {"type": "json_object"}


async def test_ollama_unavailable_without_fallback(install_transport: InstallTransport) -> None:
    def offline(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("private details", request=request)

    requests = install_transport(offline)
    settings = Settings(
        AI_PROVIDER="ollama", AI_MAX_RETRIES=0, OPENAI_API_KEY=SecretStr("mock-value")
    )
    provider = ProviderFactory.create(settings)
    assert not (await provider.check_availability()).available
    with pytest.raises(ProviderUnavailableError, match="ollama") as error:
        await provider.generate("prompt")
    assert error.value.error_code == "PROVIDER_UNAVAILABLE"
    assert "private details" not in str(error.value)
    assert [request.url.host for request in requests] == ["localhost", "localhost"]


@pytest.mark.parametrize(
    ("status", "body", "error_type"),
    [
        (401, {"error": "mock-value"}, ProviderAuthError),
        (429, {"error": {"message": "mock-value"}}, ProviderRateLimitError),
        (429, {"error": {"code": "insufficient_quota"}}, ProviderQuotaError),
        (200, {"choices": []}, ProviderMalformedResponseError),
    ],
)
async def test_openai_normalizes_errors(
    install_transport: InstallTransport,
    caplog: pytest.LogCaptureFixture,
    status: int,
    body: dict[str, object],
    error_type: type[ProviderError],
) -> None:
    requests = install_transport(lambda _: httpx.Response(status, json=body))
    settings = Settings(
        AI_PROVIDER="openai",
        OPENAI_API_KEY=SecretStr("mock-value"),
        AI_MAX_RETRIES=0 if error_type is ProviderRateLimitError else 2,
    )
    with pytest.raises(error_type) as error:
        await ProviderFactory.create(settings).generate("private prompt")
    assert len(requests) == 1
    assert error.value.__suppress_context__ or error.value.__context__ is None
    for secret in ("mock-value", "private prompt"):
        assert secret not in str(error.value) and secret not in caplog.text


@pytest.mark.parametrize("content", ["not json", "[1]", '{"bad":NaN}', 1])
async def test_ollama_rejects_invalid_structured_output(
    install_transport: InstallTransport, content: object
) -> None:
    requests = install_transport(lambda _: httpx.Response(200, json={"response": content}))
    with pytest.raises(ProviderMalformedResponseError):
        await ProviderFactory.create(Settings()).generate(
            "Return JSON", GenerationOptions(json_output=True)
        )
    assert len(requests) == 1


async def test_ollama_retries_twice(
    install_transport: InstallTransport, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise httpx.ConnectError("unreachable", request=request)
        return httpx.Response(200, json={"response": "success"})

    requests = install_transport(respond)
    clock = Mock(wraps=asyncio)
    clock.sleep = AsyncMock()
    monkeypatch.setattr(provider_http, "asyncio", clock)
    assert (await ProviderFactory.create(Settings()).generate("prompt")).usage is None
    assert len(requests) == 3
    assert clock.sleep.await_args_list == [call(1), call(2)]


async def test_retry_budget_includes_backoff(install_transport: InstallTransport) -> None:
    requests = install_transport(lambda _: httpx.Response(503))
    settings = Settings(AI_RETRY_BUDGET_SECONDS=1, AI_REQUEST_TIMEOUT_SECONDS=5)
    async with asyncio.timeout(2):
        with pytest.raises(ProviderTimeoutError):
            await ProviderFactory.create(settings).generate("prompt")
    assert len(requests) == 1


async def test_provider_timeout_and_cancellation(install_transport: InstallTransport) -> None:
    started = asyncio.Event()

    async def respond(_: httpx.Request) -> httpx.Response:
        started.set()
        await asyncio.Event().wait()
        pytest.fail("expected cancellation")

    install_transport(respond)
    provider = ProviderFactory.create(Settings(AI_REQUEST_TIMEOUT_SECONDS=1))
    with pytest.raises(ProviderTimeoutError):
        await provider.generate("prompt")
    started.clear()
    task = asyncio.create_task(provider.generate("prompt"))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_http_timeout_is_not_retried(install_transport: InstallTransport) -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("private details", request=request)

    requests = install_transport(timeout)
    with pytest.raises(ProviderTimeoutError):
        await ProviderFactory.create(Settings()).generate("prompt")
    assert len(requests) == 1
