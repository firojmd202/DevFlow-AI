"""Workflow approval repository name, kept separate from MCP authorization."""

from devflow_api.repositories.approval import ApprovalRepository as ApprovalRequestRepository

__all__ = ["ApprovalRequestRepository"]
