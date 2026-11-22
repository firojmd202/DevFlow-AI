"""Provider failures with public messages independent of request and response data."""

from devflow_core.exceptions import DevFlowError


class ProviderError(DevFlowError):
    error_code = "PROVIDER_ERROR"
    description = "request failed"

    def __init__(self, provider_id: str, model_id: str) -> None:
        self.provider_id = provider_id
        self.model_id = model_id
        self.message = f"{provider_id}: {self.description}"
        super().__init__(self.message)


class ProviderConfigurationError(ProviderError):
    error_code = "PROVIDER_NOT_CONFIGURED"
    description = "invalid or missing configuration"


class ProviderUnavailableError(ProviderError):
    error_code = "PROVIDER_UNAVAILABLE"
    description = "service or model unavailable"

    def __init__(self, provider_id: str, model_id: str, *, transient: bool = False) -> None:
        super().__init__(provider_id, model_id)
        self.transient = transient


class ProviderTimeoutError(ProviderError):
    error_code = "PROVIDER_TIMEOUT"
    description = "request timed out"


class ProviderCancelledError(ProviderError):
    error_code = "PROVIDER_CANCELLED"
    description = "request cancelled"


class ProviderQuotaError(ProviderError):
    error_code = "PROVIDER_QUOTA_EXCEEDED"
    description = "quota exhausted"


class ProviderAuthError(ProviderError):
    error_code = "PROVIDER_AUTH_FAILED"
    description = "authentication failed"


class ProviderMalformedResponseError(ProviderError):
    error_code = "PROVIDER_MALFORMED_RESPONSE"
    description = "invalid generation response"


class ProviderRateLimitError(ProviderError):
    error_code = "PROVIDER_RATE_LIMITED"
    description = "rate limit exceeded"
