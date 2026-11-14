"""Offline Stitch adapter."""

from devflow_api.adapters.capability import ExecutionMode, IntegrationCapability
from devflow_api.adapters.stubs._base import OfflineAdapter


class StitchStubAdapter(OfflineAdapter):
    _capability = IntegrationCapability(
        name="stitch",
        execution_mode=ExecutionMode.UNKNOWN,
        supported_actions=[],
        auth_required=False,
        auth_type=None,
        available_in_phase_0=False,
    )
