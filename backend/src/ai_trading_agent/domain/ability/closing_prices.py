"""Persistence boundary for provider-neutral, unadjusted closing observations."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.aggregate.technical import PriceBar


@dataclass(frozen=True)
class ClosingPrices:
    instrument: Instrument
    source: str
    fetched_at: datetime
    bars: tuple[PriceBar, ...]


class ClosingPriceRepository(Protocol):
    async def get(self, instrument: Instrument) -> ClosingPrices | None: ...
    async def save(self, snapshot: ClosingPrices) -> None: ...
