"""ChatGPT integration contract."""

from typing import Protocol

from pydantic import BaseModel

from devflow_api.adapters.protocols.base import BaseAdapterProtocol


class ChatGPTResponse(BaseModel):
    stub: bool = True


class ChatGPTAdapterProtocol(BaseAdapterProtocol, Protocol):
    async def complete(self, prompt: str, model: str) -> ChatGPTResponse: ...
