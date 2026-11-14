"""Shared HTTP response models."""

from typing import Literal

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    error: str
    code: str


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
