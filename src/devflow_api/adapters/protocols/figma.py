"""Figma integration contract."""

from typing import Protocol

from pydantic import BaseModel

from devflow_api.adapters.protocols.base import BaseAdapterProtocol


class FigmaResponse(BaseModel):
    stub: bool = True


class FigmaAdapterProtocol(BaseAdapterProtocol, Protocol):
    async def get_file(self, file_key: str) -> FigmaResponse: ...
