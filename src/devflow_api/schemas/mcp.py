"""Wave 2 MCP context data."""

from pydantic import BaseModel


class ContextChunk(BaseModel):
    content: str
    server: str
    tool: str
    required: bool
    truncated: bool
