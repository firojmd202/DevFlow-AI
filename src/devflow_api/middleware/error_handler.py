"""Safe, consistent JSON errors for the HTTP API."""

from http import HTTPStatus
from traceback import extract_tb

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.utils import is_body_allowed_for_status_code
from starlette.exceptions import HTTPException

from devflow_api.schemas.common import ErrorResponse
from devflow_core.logging import get_logger


def _error(status: int, message: str, code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status, content=ErrorResponse(error=message, code=code).model_dump()
    )


async def _http_error(request: Request, exc: Exception) -> Response:
    if not isinstance(exc, HTTPException):
        raise exc
    if not is_body_allowed_for_status_code(exc.status_code):
        return Response(status_code=exc.status_code, headers=exc.headers)
    try:
        status = HTTPStatus(exc.status_code)
    except ValueError:
        message, code = "HTTP error", "HTTP_ERROR"
    else:
        message, code = status.phrase, status.name
    if exc.status_code == 404:
        message = "Not found"
    response = _error(exc.status_code, message, code)
    if exc.headers:
        response.headers.update(exc.headers)
    return response


async def _validation_error(request: Request, exc: Exception) -> JSONResponse:
    return _error(422, "Validation error", "VALIDATION_ERROR")


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    frames = extract_tb(exc.__traceback__)
    get_logger(__name__).error(
        "Unhandled request exception",
        request_id=getattr(request.state, "request_id", None),
        exception_type=type(exc).__name__,
        traceback=[f"{frame.name}:{frame.lineno}" for frame in frames],
    )
    return _error(500, "Internal server error", "INTERNAL_ERROR")


def add_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
