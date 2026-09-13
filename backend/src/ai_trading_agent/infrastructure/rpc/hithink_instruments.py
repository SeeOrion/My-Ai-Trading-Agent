"""同花顺元信息适配器：将用户的股票或基金代码映射为展示名称。"""

from __future__ import annotations

from ai_trading_agent.domain.aggregate.instrument_identity import (
    CatalogInstrument,
    InstrumentIdentity,
)
from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.enums.market import InstrumentType, Market
from ai_trading_agent.infrastructure.config.providers import HithinkFinanceSettings
from ai_trading_agent.infrastructure.rpc.hithink_client import (
    HithinkFinanceRestClient,
    HithinkFinanceServiceError,
    ResponseFetcher,
    response_items,
)

_TICKER_SEARCH_PATH = "/api/meta/tickers/search"


class HithinkInstrumentIdentityProviderError(HithinkFinanceServiceError):
    pass


class HithinkInstrumentIdentityProvider:
    """Resolve only types the official Hithink meta catalogue covers."""

    name = "hithink_finance_meta"

    def __init__(
        self, settings: HithinkFinanceSettings, *, response_fetcher: ResponseFetcher | None = None
    ) -> None:
        self._client = HithinkFinanceRestClient(settings, response_fetcher=response_fetcher)

    async def resolve(self, instrument: Instrument) -> InstrumentIdentity | None:
        asset_type = _asset_type(instrument)
        if asset_type is None:
            return None
        try:
            data = await self._client.get(
                _TICKER_SEARCH_PATH,
                {"q": instrument.symbol, "asset_type": asset_type, "limit": 10},
            )
        except HithinkFinanceServiceError as error:
            raise HithinkInstrumentIdentityProviderError(str(error)) from error
        row = _best_match(response_items(data), instrument)
        if row is None:
            return None
        return InstrumentIdentity(instrument, str(row["name"]), self.name)

    async def search(
        self, query: str, *, asset_types: tuple[str, ...], limit: int
    ) -> list[CatalogInstrument]:
        """Search the documented catalogue without guessing codes or exchanges."""
        try:
            data = await self._client.get(
                _TICKER_SEARCH_PATH,
                {"q": query, "asset_type": ",".join(asset_types), "limit": limit},
            )
        except HithinkFinanceServiceError as error:
            raise HithinkInstrumentIdentityProviderError(str(error)) from error
        matches: list[CatalogInstrument] = []
        seen: set[str] = set()
        allowed = {asset_type.lower() for asset_type in asset_types}
        for row in response_items(data):
            candidate = _catalog_item(row)
            if candidate is None or candidate.asset_type not in allowed:
                continue
            if candidate.symbol in seen:
                continue
            seen.add(candidate.symbol)
            matches.append(candidate)
        return matches


def _asset_type(instrument: Instrument) -> str | None:
    if instrument.market is Market.A_SHARE and instrument.instrument_type is InstrumentType.EQUITY:
        return "a-share"
    if instrument.instrument_type is InstrumentType.ETF:
        return "fund-etf,fund-lof"
    if instrument.market is Market.FUND and instrument.instrument_type is InstrumentType.FUND:
        return "fund-otc"
    return None


def _best_match(rows: list[dict[str, object]], instrument: Instrument) -> dict[str, object] | None:
    canonical = instrument.symbol.upper()
    ticker = canonical.split(".", maxsplit=1)[0]
    exact = [
        row
        for row in rows
        if str(row.get("thscode", "")).upper() == canonical and str(row.get("name", "")).strip()
    ]
    if exact:
        return exact[0]
    ticker_matches = [
        row
        for row in rows
        if str(row.get("ticker", "")).upper() == ticker and str(row.get("name", "")).strip()
    ]
    return ticker_matches[0] if len(ticker_matches) == 1 else None


def _catalog_item(row: dict[str, object]) -> CatalogInstrument | None:
    symbol = str(row.get("thscode", "")).strip()
    name = str(row.get("name", "")).strip()
    asset_type = str(row.get("asset_type", "")).strip()
    if not symbol or not name or not asset_type:
        return None
    return CatalogInstrument(
        symbol=symbol,
        name=name,
        asset_type=asset_type,
        exchange=_optional_string(row.get("exchange")),
        currency=_optional_string(row.get("currency")),
        source=HithinkInstrumentIdentityProvider.name,
    )


def _optional_string(value: object) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None
