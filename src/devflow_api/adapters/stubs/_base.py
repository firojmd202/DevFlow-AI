"""Capability and health behavior shared by offline adapters."""

from typing import ClassVar

from devflow_api.adapters.capability import IntegrationCapability


class OfflineAdapter:
    _capability: ClassVar[IntegrationCapability]

    @property
    def name(self) -> str:
        return self._capability.name

    @property
    def capability(self) -> IntegrationCapability:
        return self._capability.model_copy(deep=True)

    async def health_check(self) -> dict[str, str]:
        return {
            "status": "stub",
            "integration": self.name,
            "execution_mode": self._capability.execution_mode,
        }
