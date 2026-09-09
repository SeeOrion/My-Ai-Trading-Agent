"""Private-key REST adapter for verified Hithink Finance A-share snapshots."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from ai_trading_agent.domain.aggregate.market import Instrument, Quote
from ai_trading_agent.domain.enums.market import InstrumentType, Market
from ai_trading_agent.infrastructure.config.providers import HithinkFinanceSettings
from ai_trading_agent.infrastructure.rpc.hithink_client import (
    HithinkFinanceRestClient,
    HithinkFinanceServiceError,
    ResponseFetcher,
    decimal_or_none,
    non_negative_decimal,
    response_items,
)


class HithinkFinanceProviderError(HithinkFinanceServiceError):
    pass


class HithinkFinanceMarketDataProvider:
    """A-share equity snapshots; key stays in the request header only."""

    name = "hithink_finance"

    def __init__(
        self, settings: HithinkFinanceSettings, *, response_fetcher: ResponseFetcher | None = None
    ) -> None:
        self._client = HithinkFinanceRestClient(settings, response_fetcher=response_fetcher)

    def supports(self, market: Market) -> bool:
        return market is Market.A_SHARE

    async def get_latest_quotes(self, instruments: Iterable[Instrument]) -> list[Quote]:
        requested = list(instruments)
        if any(
            item.market is not Market.A_SHARE or item.instrument_type is not InstrumentType.EQUITY
            for item in requested
        ):
            raise HithinkFinanceProviderError(
                "Hithink snapshot adapter currently supports A-share equities"
            )
        if not requested:
            return []
        try:
            data = await self._client.get(
                "/api/a-share/prices/snapshot",
                {"thscodes": ",".join(item.symbol for item in requested)},
            )
        except HithinkFinanceServiceError as error:
            raise HithinkFinanceProviderError(str(error)) from error
        rows = {str(row.get("thscode")): row for row in response_items(data)}
        return [_quote(item, rows.get(item.symbol)) for item in requested]


def _quote(instrument: Instrument, row: object) -> Quote:
    if not isinstance(row, dict):
        raise HithinkFinanceProviderError(f"snapshot response omitted: {instrument.symbol}")
    return Quote(
        instrument=instrument,
        last_price=non_negative_decimal(row.get("last_price"), "last_price"),
        observed_at=datetime.now(UTC),
        source="hithink_finance",
        open_price=decimal_or_none(row.get("open_price"), "open_price"),
        high_price=decimal_or_none(row.get("high_price"), "high_price"),
        low_price=decimal_or_none(row.get("low_price"), "low_price"),
        previous_close=decimal_or_none(row.get("prev_price"), "prev_price"),
        volume=decimal_or_none(row.get("volume"), "volume"),
    )
