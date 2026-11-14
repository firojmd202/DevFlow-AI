"""Offline NotebookLM adapter."""

from devflow_api.adapters.capability import ExecutionMode, IntegrationCapability
from devflow_api.adapters.stubs._base import OfflineAdapter


class NotebookLMStubAdapter(OfflineAdapter):
    _capability = IntegrationCapability(
        name="notebooklm",
        execution_mode=ExecutionMode.MANUAL_HANDOFF,
        supported_actions=["get_instructions"],
        auth_required=False,
        auth_type=None,
        available_in_phase_0=False,
    )

    def get_instructions(self, notebook_context: str) -> str:
        return (
            f"[Phase 0 stub] Open NotebookLM and select sources for {notebook_context!r}. "
            "Review the results in the notebook."
        )
