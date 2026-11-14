"""Claude integration contract."""

from typing import Protocol

from pydantic import BaseModel

from devflow_api.adapters.protocols.base import BaseAdapterProtocol


class ClaudeResponse(BaseModel):
    stub: bool = True


class ClaudeAdapterProtocol(BaseAdapterProtocol, Protocol):
    async def complete(self, prompt: str, model: str) -> ClaudeResponse: ...
