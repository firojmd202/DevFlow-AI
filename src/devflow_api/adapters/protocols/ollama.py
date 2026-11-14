"""Ollama integration contract."""

from typing import Protocol

from pydantic import BaseModel

from devflow_api.adapters.protocols.base import BaseAdapterProtocol


class OllamaResponse(BaseModel):
    stub: bool = True


class OllamaAdapterProtocol(BaseAdapterProtocol, Protocol):
    async def generate(self, model: str, prompt: str) -> OllamaResponse: ...
