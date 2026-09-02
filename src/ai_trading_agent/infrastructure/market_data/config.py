"""Configuration for market-data adapters.

Credentials are intentionally read only at composition time. Domain and
application modules never import this module or environment variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


class ProviderConfigurationError(RuntimeError):
    """Raised when an adapter is selected without its required configuration."""


@dataclass(frozen=True, slots=True)
class TushareSettings:
    token: str

    @classmethod
    def from_environment(cls) -> TushareSettings:
        token = os.environ.get("TUSHARE_TOKEN", "").strip()
        if not token:
            raise ProviderConfigurationError("TUSHARE_TOKEN is required for the Tushare adapter")
        return cls(token=token)


@dataclass(frozen=True, slots=True)
class FutuSettings:
    host: str = "127.0.0.1"
    port: int = 11111

    @classmethod
    def from_environment(cls) -> FutuSettings:
        host = os.environ.get("FUTU_OPEND_HOST", "127.0.0.1").strip()
        raw_port = os.environ.get("FUTU_OPEND_PORT", "11111").strip()
        if not host:
            raise ProviderConfigurationError("FUTU_OPEND_HOST must not be empty")
        try:
            port = int(raw_port)
        except ValueError as error:
            raise ProviderConfigurationError("FUTU_OPEND_PORT must be an integer") from error
        if not 1 <= port <= 65535:
            raise ProviderConfigurationError("FUTU_OPEND_PORT must be between 1 and 65535")
        return cls(host=host, port=port)
