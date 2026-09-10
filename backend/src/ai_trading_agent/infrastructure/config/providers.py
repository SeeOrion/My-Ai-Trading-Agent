"""Configuration for market-data adapters.

Credentials are intentionally read only at composition time. Domain and
application modules never import this module or environment variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from math import isfinite
from pathlib import Path


class ProviderConfigurationError(RuntimeError):
    """Raised when an adapter is selected without its required configuration."""


@dataclass(frozen=True, slots=True)
class HithinkFinanceSettings:
    """Read the unified key from a private user-level source, never the project."""

    api_key: str
    timeout_seconds: float = 8.0

    @classmethod
    def from_environment(cls) -> HithinkFinanceSettings:
        key = os.environ.get("HITHINK_FINANCE_API_KEY", "").strip()
        if not key:
            key = _read_hithink_user_credential()
        if not key:
            raise ProviderConfigurationError(
                "Hithink Finance credential is not configured in the private user credential store"
            )
        return cls(
            key,
            _positive_float(
                os.environ.get("HITHINK_FINANCE_TIMEOUT_SECONDS", "8"),
                "HITHINK_FINANCE_TIMEOUT_SECONDS",
            ),
        )


def _read_hithink_user_credential() -> str:
    path = Path.home() / "Library/Application Support/hithink-finance/credentials.env"
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            name, separator, value = line.partition("=")
            if separator and name.strip() == "HITHINK_FINANCE_API_KEY":
                return value.strip()
    except OSError:
        return ""
    return ""


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
class TencentQuoteSettings:
    """No-credential controls for the experimental public quote fallback."""

    timeout_seconds: float = 5.0

    @classmethod
    def from_environment(cls) -> TencentQuoteSettings:
        return cls(
            timeout_seconds=_positive_float(
                os.environ.get("TENCENT_QUOTE_TIMEOUT_SECONDS", "5").strip(),
                "TENCENT_QUOTE_TIMEOUT_SECONDS",
            )
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


@dataclass(frozen=True, slots=True)
class MarketScanSettings:
    """Bounded controls for manual and scheduled market-wide scans."""

    futu_batch_size: int = 400
    scheduler_enabled: bool = False
    interval_seconds: int = 900

    @classmethod
    def from_environment(cls) -> MarketScanSettings:
        raw_enabled = os.environ.get("MARKET_SCAN_SCHEDULER_ENABLED", "false").strip().lower()
        if raw_enabled not in {"true", "false"}:
            raise ProviderConfigurationError("MARKET_SCAN_SCHEDULER_ENABLED must be true or false")
        return cls(
            futu_batch_size=_bounded_int(
                os.environ.get("FUTU_SCAN_BATCH_SIZE", "400").strip(),
                "FUTU_SCAN_BATCH_SIZE",
                minimum=1,
                maximum=400,
            ),
            scheduler_enabled=raw_enabled == "true",
            interval_seconds=_bounded_int(
                os.environ.get("MARKET_SCAN_INTERVAL_SECONDS", "900").strip(),
                "MARKET_SCAN_INTERVAL_SECONDS",
                minimum=60,
                maximum=86_400,
            ),
        )


@dataclass(frozen=True, slots=True)
class WatchlistAnalysisSettings:
    """Bounded cadence for selected-instrument research refreshes only."""

    scheduler_enabled: bool = True
    interval_seconds: int = 900
    max_items_per_run: int = 30

    @classmethod
    def from_environment(cls) -> WatchlistAnalysisSettings:
        raw_enabled = os.environ.get(
            "WATCHLIST_ANALYSIS_SCHEDULER_ENABLED", "true"
        ).strip().lower()
        if raw_enabled not in {"true", "false"}:
            raise ProviderConfigurationError(
                "WATCHLIST_ANALYSIS_SCHEDULER_ENABLED must be true or false"
            )
        return cls(
            scheduler_enabled=raw_enabled == "true",
            interval_seconds=_bounded_int(
                os.environ.get("WATCHLIST_ANALYSIS_INTERVAL_SECONDS", "900").strip(),
                "WATCHLIST_ANALYSIS_INTERVAL_SECONDS",
                minimum=300,
                maximum=86_400,
            ),
            max_items_per_run=_bounded_int(
                os.environ.get("WATCHLIST_ANALYSIS_MAX_ITEMS", "30").strip(),
                "WATCHLIST_ANALYSIS_MAX_ITEMS",
                minimum=1,
                maximum=100,
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


def _bounded_int(value: str, name: str, *, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise ProviderConfigurationError(f"{name} must be an integer") from error
    if not minimum <= parsed <= maximum:
        raise ProviderConfigurationError(f"{name} must be between {minimum} and {maximum}")
    return parsed
