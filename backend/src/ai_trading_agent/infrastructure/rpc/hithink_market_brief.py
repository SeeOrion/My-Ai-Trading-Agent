"""同花顺指数快照适配器：指数总览与行业板块涨跌排序。"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import UTC, datetime

from ai_trading_agent.domain.aggregate.market_brief import (
    IndexSnapshot,
    PostMarketBrief,
    SectorPerformance,
)
from ai_trading_agent.infrastructure.config.providers import HithinkFinanceSettings
from ai_trading_agent.infrastructure.rpc.hithink_client import (
    HithinkFinanceRestClient,
    HithinkFinanceServiceError,
    ResponseFetcher,
    datetime_from_milliseconds,
    decimal_or_none,
    non_negative_decimal,
    response_items,
)

_INDEX_SNAPSHOT_PATH = "/api/a-share-index/prices/snapshot"
_INDUSTRY_CATALOG_PATH = "/api/a-share-index/catalog/ths-index-list"
_SNAPSHOT_BATCH_SIZE = 80
_BENCHMARKS = (
    ("000001.SH", "上证综指"),
    ("399001.SZ", "深证成指"),
    ("399006.SZ", "创业板指"),
    ("000300.SH", "沪深 300"),
)


class HithinkMarketBriefProviderError(HithinkFinanceServiceError):
    """Raised when the upstream index response cannot form a usable brief."""


class HithinkMarketBriefProvider:
    """Use documented index endpoints; no full stock-market scan is performed."""

    name = "hithink_finance_index"

    def __init__(
        self, settings: HithinkFinanceSettings, *, response_fetcher: ResponseFetcher | None = None
    ) -> None:
        self._client = HithinkFinanceRestClient(settings, response_fetcher=response_fetcher)

    async def get_post_market_brief(self) -> PostMarketBrief:
        try:
            benchmark_data, catalog_data = await asyncio.gather(
                self._client.get(
                    _INDEX_SNAPSHOT_PATH,
                    {"thscodes": ",".join(symbol for symbol, _ in _BENCHMARKS)},
                ),
                self._client.get(_INDUSTRY_CATALOG_PATH, {"tag": "industry"}),
            )
            benchmark_rows = _rows_by_symbol(response_items(benchmark_data))
            indices = tuple(
                _index_snapshot(symbol, name, benchmark_rows.get(symbol))
                for symbol, name in _BENCHMARKS
            )
            sectors = _catalog_sectors(response_items(catalog_data))
            sector_rows = await self._get_snapshot_rows(symbol for symbol, _ in sectors)
        except HithinkFinanceServiceError as error:
            raise HithinkMarketBriefProviderError(str(error)) from error

        performances = tuple(
            _sector_performance(symbol, name, sector_rows.get(symbol))
            for symbol, name in sectors
            if sector_rows.get(symbol) is not None
        )
        if not performances:
            raise HithinkMarketBriefProviderError(
                "industry snapshot response omitted usable sectors"
            )
        ranked = tuple(sorted(performances, key=lambda item: item.change_percent, reverse=True))
        observed_at = (
            datetime_from_milliseconds(benchmark_data.get("timestamp"), "timestamp")
            or datetime_from_milliseconds(catalog_data.get("timestamp"), "timestamp")
            or datetime.now(UTC)
        )
        return PostMarketBrief(
            observed_at=observed_at,
            source=self.name,
            indices=indices,
            leading_sectors=ranked[:3],
            lagging_sectors=tuple(reversed(ranked[-3:])),
        )

    async def _get_snapshot_rows(self, symbols: Iterable[str]) -> dict[str, dict[str, object]]:
        requested = tuple(symbols)
        if not requested:
            raise HithinkMarketBriefProviderError("industry catalog was empty")
        batches = [
            requested[index : index + _SNAPSHOT_BATCH_SIZE]
            for index in range(0, len(requested), _SNAPSHOT_BATCH_SIZE)
        ]
        responses = await asyncio.gather(
            *(
                self._client.get(_INDEX_SNAPSHOT_PATH, {"thscodes": ",".join(batch)})
                for batch in batches
            )
        )
        rows: dict[str, dict[str, object]] = {}
        for response in responses:
            rows.update(_rows_by_symbol(response_items(response)))
        return rows


def _rows_by_symbol(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {str(row.get("thscode")).upper(): row for row in rows if row.get("thscode")}


def _catalog_sectors(rows: list[dict[str, object]]) -> tuple[tuple[str, str], ...]:
    sectors = tuple(
        (str(row.get("thscode")).upper(), str(row.get("name")).strip())
        for row in rows
        if row.get("thscode") and str(row.get("name", "")).strip()
    )
    if not sectors:
        raise HithinkMarketBriefProviderError("industry catalog response omitted sectors")
    return sectors


def _index_snapshot(symbol: str, name: str, row: object) -> IndexSnapshot:
    if not isinstance(row, dict):
        raise HithinkMarketBriefProviderError(f"snapshot response omitted: {symbol}")
    return IndexSnapshot(
        symbol=symbol,
        name=name,
        last_price=non_negative_decimal(row.get("last_price"), "last_price"),
        price_change=decimal_or_none(row.get("price_change"), "price_change"),
        change_percent=decimal_or_none(
            row.get("price_change_ratio_pct"), "price_change_ratio_pct"
        ),
    )


def _sector_performance(symbol: str, name: str, row: object) -> SectorPerformance:
    if not isinstance(row, dict):
        raise HithinkMarketBriefProviderError(f"industry snapshot response omitted: {symbol}")
    change_percent = decimal_or_none(row.get("price_change_ratio_pct"), "price_change_ratio_pct")
    if change_percent is None:
        raise HithinkMarketBriefProviderError(f"industry snapshot omitted change: {symbol}")
    return SectorPerformance(
        symbol=symbol,
        name=name,
        last_price=non_negative_decimal(row.get("last_price"), "last_price"),
        change_percent=change_percent,
    )
