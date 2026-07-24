from __future__ import annotations

from typing import Any


class ProviderError(Exception):
    category = "provider"
    retryable = False

    def __init__(self, operation: str, message: str, *, details: Any = None):
        super().__init__(f"Provider {operation} failed: {message}")
        self.operation = operation
        self.message = message
        self.details = details


class ProviderInputError(ProviderError):
    category = "input_validation"


class ProviderOutputError(ProviderError):
    category = "output_validation"


class ProviderTransportError(ProviderError):
    category = "transport"
    retryable = True


class ProviderResponseError(ProviderError):
    category = "invalid_response"
