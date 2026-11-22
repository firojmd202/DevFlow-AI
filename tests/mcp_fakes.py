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
        self.calls: list[str] = []
        self.tool_started = asyncio.Event()
        self.pong = asyncio.Event()
        self.tool_text = "result"
        self._pending_response: dict[str, object] | None = None

    def send(self, message: dict[str, object]) -> None:
        self.stdout.feed_data((json.dumps({"jsonrpc": "2.0", **message}) + "\n").encode())

    def write(self, document: bytes) -> None:
        request = json.loads(document)
        if request.get("id") == "server-ping" and request.get("result") == {}:
            self.pong.set()
            if self._pending_response is not None:
                self.send(self._pending_response)
                self._pending_response = None
            return
        method = request.get("method")
        if isinstance(method, str):
            self.calls.append(method)
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
            if self.outcome == "no_tools":
                result["capabilities"] = {}
        elif request["method"] == "tools/list":
            if self.outcome == "paginated" and not request.get("params", {}).get("cursor"):
                self.send(
                    {
                        "id": request["id"],
                        "result": {
                            "nextCursor": "next",
                            "tools": [{"name": "write", "inputSchema": {"type": "object"}}],
                        },
                    }
                )
                return
            result = {
                "tools": [
                    {"name": name, "inputSchema": {"type": "object"}} for name in ("read", "write")
                ]
            }
        else:
            self.tool_started.set()
            self.arguments = request["params"].get("arguments")
            if self.outcome == "stall":
                return
            if self.outcome == "error":
                self.send(
                    {
                        "id": request["id"],
                        "error": {"code": -32602, "message": "private protocol detail"},
                    }
                )
                return
            result = {"content": [{"type": "text", "text": self.tool_text}]}
            if self.outcome == "input_required":
                result = {"resultType": "input_required", "requestState": "private state"}
            if self.outcome == "unexpected":
                result["resultType"] = "unexpected"
            if self.outcome == "protocol":
                self._pending_response = {"id": request["id"], "result": result}
                self.send({"method": "ping", "id": "server-ping"})
                self.send(
                    {
                        "method": "notifications/message",
                        "params": {"level": "info", "data": "private server log"},
                    }
                )
                self.send(
                    {
                        "method": "notifications/message",
                        "params": {"level": "invalid", "data": "private malformed log"},
                    }
                )
                return
        self.send({"id": request["id"], "result": result})

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
