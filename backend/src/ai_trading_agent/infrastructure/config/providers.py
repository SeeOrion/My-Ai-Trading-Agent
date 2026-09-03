"""Configuration for market-data adapters.

Credentials are intentionally read only at composition time. Domain and
application modules never import this module or environment variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from math import isfinite


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
    connect_timeout_seconds: float = 2.0

    @classmethod
    def from_environment(cls) -> FutuSettings:
        host = os.environ.get("FUTU_OPEND_HOST", "127.0.0.1").strip()
        raw_port = os.environ.get("FUTU_OPEND_PORT", "11111").strip()
        raw_timeout = os.environ.get("FUTU_OPEND_CONNECT_TIMEOUT_SECONDS", "2").strip()
        if not host:
            raise ProviderConfigurationError("FUTU_OPEND_HOST must not be empty")
        try:
            port = int(raw_port)
        except ValueError as error:
            raise ProviderConfigurationError("FUTU_OPEND_PORT must be an integer") from error
        if not 1 <= port <= 65535:
            raise ProviderConfigurationError("FUTU_OPEND_PORT must be between 1 and 65535")
        return cls(
            host=host,
            port=port,
            connect_timeout_seconds=_positive_float(
                raw_timeout, "FUTU_OPEND_CONNECT_TIMEOUT_SECONDS"
            ),
        )


@dataclass(frozen=True, slots=True)
class AShareQuoteFailoverSettings:
    futu_timeout_seconds: float = 5.0
    futu_cooldown_seconds: float = 60.0

    @classmethod
    def from_environment(cls) -> AShareQuoteFailoverSettings:
        return cls(
            futu_timeout_seconds=_positive_float(
                os.environ.get("A_SHARE_FUTU_TIMEOUT_SECONDS", "5").strip(),
                "A_SHARE_FUTU_TIMEOUT_SECONDS",
            ),
            futu_cooldown_seconds=_positive_float(
                os.environ.get("A_SHARE_FUTU_COOLDOWN_SECONDS", "60").strip(),
                "A_SHARE_FUTU_COOLDOWN_SECONDS",
            ),
        )


def _positive_float(value: str, name: str) -> float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise ProviderConfigurationError(f"{name} must be a number") from error
    if not isfinite(parsed) or parsed <= 0:
        raise ProviderConfigurationError(f"{name} must be positive")
    return parsed
