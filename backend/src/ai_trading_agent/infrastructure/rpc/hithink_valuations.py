"""Small A-share valuation adapter used by the factor-analysis context."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.infrastructure.config.providers import HithinkFinanceSettings
from ai_trading_agent.infrastructure.rpc.hithink_client import (
    HithinkFinanceRestClient,
    HithinkFinanceServiceError,
    ResponseFetcher,
    decimal_or_none,
    response_items,
)


class HithinkAshareValuationProviderError(HithinkFinanceServiceError):
    pass


@dataclass(frozen=True, slots=True)
class ValuationSnapshot:
    """The two point-in-time valuation inputs used by the default factor set."""

    pe_ttm: Decimal | None
    pb_mrq: Decimal | None
    source: str = "hithink_finance"


class HithinkAshareValuationProvider:
    """Request only the documented valuation snapshot, not the full detail workspace."""

    name = "hithink_finance"

    def __init__(
        self, settings: HithinkFinanceSettings, *, response_fetcher: ResponseFetcher | None = None
    ) -> None:
        self._client = HithinkFinanceRestClient(settings, response_fetcher=response_fetcher)

    async def get_valuation_snapshot(self, instrument: Instrument) -> ValuationSnapshot:
        if instrument.market is not Market.A_SHARE:
            raise HithinkAshareValuationProviderError("Hithink valuations only support A-share")
        try:
            data = await self._client.get(
                "/api/a-share/valuations/snapshot", {"thscodes": instrument.symbol}
            )
            rows = response_items(data)
            if not rows:
                raise HithinkAshareValuationProviderError(
                    f"valuation response omitted: {instrument.symbol}"
                )
            row = rows[0]
            return ValuationSnapshot(
                pe_ttm=decimal_or_none(row.get("pe_ttm"), "pe_ttm"),
                pb_mrq=decimal_or_none(row.get("pb_mrq"), "pb_mrq"),
            )
        except HithinkFinanceServiceError as error:
            raise HithinkAshareValuationProviderError(str(error)) from error
