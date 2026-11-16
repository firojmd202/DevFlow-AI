import asyncio
import json
from unittest.mock import AsyncMock, Mock


class FakeServer:
    """Pipe-level fake which exchanges real SDK JSON-RPC messages."""

    def __init__(self, outcome: str = "success") -> None:
        self.outcome = outcome
        self.stdout = asyncio.StreamReader()
        self.stdin = Mock(write=self.write, drain=AsyncMock(), close=Mock())
        self.returncode: int | None = None
        self.terminated = False
        self.killed = False
        self.arguments: object = None

    def write(self, document: bytes) -> None:
        request = json.loads(document)
        if "id" not in request or self.outcome == "timeout":
            return
        if self.outcome == "invalid":
            self.stdout.feed_data(b"not JSON\n")
            return
        if request["method"] == "initialize":
            result = {
                "protocolVersion": request["params"]["protocolVersion"],
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fake", "version": "1"},
            }
        elif request["method"] == "tools/list":
            result = {
                "tools": [
                    {"name": name, "inputSchema": {"type": "object"}} for name in ("read", "write")
                ]
            }
        else:
            self.arguments = request["params"].get("arguments")
            result = {"content": [{"type": "text", "text": "result"}]}
        self.stdout.feed_data(
            (json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}) + "\n").encode()
        )

    def terminate(self) -> None:
        self.terminated = True
        if self.outcome != "timeout":
            self.returncode = 0

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    async def communicate(self) -> tuple[bytes, bytes]:
        while self.returncode is None:
            await asyncio.sleep(0)
        return b"", b""
