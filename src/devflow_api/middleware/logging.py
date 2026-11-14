"""Request-scoped structured logging."""

from time import perf_counter
from uuid import uuid4

from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from structlog.contextvars import bind_contextvars, reset_contextvars

from devflow_api.middleware.error_handler import handle_unexpected_error
from devflow_core.logging import get_logger


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        context = bind_contextvars(request_id=request_id)
        start = perf_counter()
        status = 500
        response_started = False

        async def capture_status(message: Message) -> None:
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                status = message["status"]
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, capture_status)
        except Exception as exc:
            response = await handle_unexpected_error(Request(scope), exc)
            if response_started:
                raise RuntimeError("HTTP response interrupted") from None
            await response(scope, receive, capture_status)
        finally:
            try:
                route = scope.get("route")
                get_logger(__name__).info(
                    "HTTP request",
                    method=scope["method"],
                    path=getattr(route, "path", "<unmatched>"),
                    status_code=status,
                    duration_ms=round((perf_counter() - start) * 1000, 3),
                    request_id=request_id,
                )
            finally:
                reset_contextvars(**context)
