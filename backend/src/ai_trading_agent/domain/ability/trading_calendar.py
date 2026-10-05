"""Domain port for exchange-specific trading sessions."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from ai_trading_agent.domain.enums.market import Market


class TradingCalendarPort(Protocol):
    """Answer trading-day and live-session questions without leaking provider details."""

    def is_trading_day(self, market: Market, observed_at: datetime) -> bool:
        """Return whether the market has a regular session on its local date."""

    def is_open(self, market: Market, observed_at: datetime) -> bool:
        """Return whether the market is in a regular session at the given instant."""
