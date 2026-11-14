"""Base contract for all adapters."""

from typing import Protocol, runtime_checkable

from devflow_api.adapters.capability import IntegrationCapability


@runtime_checkable
class BaseAdapterProtocol(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def capability(self) -> IntegrationCapability: ...

    async def health_check(self) -> dict[str, str]: ...
