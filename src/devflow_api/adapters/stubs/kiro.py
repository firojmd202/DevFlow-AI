"""Offline Kiro adapter."""

from devflow_api.adapters.capability import ExecutionMode, IntegrationCapability
from devflow_api.adapters.stubs._base import OfflineAdapter


class KiroStubAdapter(OfflineAdapter):
    _capability = IntegrationCapability(
        name="kiro",
        execution_mode=ExecutionMode.MANUAL_HANDOFF,
        supported_actions=["get_instructions"],
        auth_required=False,
        auth_type=None,
        available_in_phase_0=False,
    )

    def get_instructions(self, task: str) -> str:
        return (
            f"[Phase 0 stub] Open the relevant specification in Kiro for {task!r}. "
            "Use the IDE to review and approve any proposed changes."
        )
