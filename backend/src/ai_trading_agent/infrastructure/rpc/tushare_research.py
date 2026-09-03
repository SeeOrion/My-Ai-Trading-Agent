"""Tushare Pro adapter for published A-share fundamentals and capital flows."""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.aggregate.research import CapitalFlowSnapshot, FinancialSnapshot
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.infrastructure.config.providers import TushareSettings


class TushareResearchProviderError(RuntimeError):
    """Raised when published Tushare research data is invalid or unavailable."""


class TushareResearchProvider:
    """Read published A-share financial indicators and L2-derived money flows."""

    name = "tushare"

    def __init__(self, settings: TushareSettings) -> None:
        self._settings = settings

    async def get_financial_snapshot(self, instrument: Instrument) -> FinancialSnapshot:
        self._require_a_share(instrument)
        return await asyncio.to_thread(self._get_financial_snapshot_sync, instrument)

    async def get_capital_flow(self, instrument: Instrument) -> CapitalFlowSnapshot:
        self._require_a_share(instrument)
        return await asyncio.to_thread(self._get_capital_flow_sync, instrument)

    def _client(self):  # type: ignore[no-untyped-def]
        try:
            import tushare as ts
        except ImportError as error:  # pragma: no cover - deployment guard
            raise TushareResearchProviderError("Tushare SDK is not installed") from error
        return ts.pro_api(self._settings.token)

    def _get_financial_snapshot_sync(self, instrument: Instrument) -> FinancialSnapshot:
        client = self._client()
        try:
            indicators = client.fina_indicator(ts_code=instrument.symbol)
            valuations = client.daily_basic(
                ts_code=instrument.symbol,
                fields="ts_code,trade_date,pe,pb",
            )
        except Exception as error:
            raise TushareResearchProviderError(
                f"fundamentals query failed for {instrument.symbol}: {error}"
            ) from error
        if indicators is None or indicators.empty:
            raise TushareResearchProviderError(f"no financial indicators for {instrument.symbol}")
        row = indicators.sort_values(["ann_date", "end_date"], ascending=False).iloc[0]
        valuation_row = None if valuations is None or valuations.empty else valuations.iloc[0]
        return FinancialSnapshot(
            instrument=instrument,
            announced_on=_parse_date(row["ann_date"], "ann_date"),
            report_period=_parse_date(row["end_date"], "end_date"),
            eps=_optional_decimal(row.get("eps"), "eps"),
            return_on_equity_pct=_optional_decimal(row.get("roe"), "roe"),
            gross_margin_pct=_optional_decimal(
                row.get("grossprofit_margin", row.get("gross_margin")), "gross margin"
            ),
            current_ratio=_optional_decimal(row.get("current_ratio"), "current_ratio"),
            net_profit_growth_pct=_optional_decimal(row.get("netprofit_yoy"), "netprofit_yoy"),
            price_to_earnings=_optional_decimal(
                None if valuation_row is None else valuation_row.get("pe"), "pe"
            ),
            price_to_book=_optional_decimal(
                None if valuation_row is None else valuation_row.get("pb"), "pb"
            ),
            source=self.name,
        )

    def _get_capital_flow_sync(self, instrument: Instrument) -> CapitalFlowSnapshot:
        client = self._client()
        try:
            frame = client.moneyflow(ts_code=instrument.symbol)
        except Exception as error:
            raise TushareResearchProviderError(
                f"capital-flow query failed for {instrument.symbol}: {error}"
            ) from error
        if frame is None or frame.empty:
            raise TushareResearchProviderError(f"no capital flow for {instrument.symbol}")
        row = frame.sort_values("trade_date", ascending=False).iloc[0]
        return CapitalFlowSnapshot(
            instrument=instrument,
            trade_date=_parse_date(row["trade_date"], "trade_date"),
            net_flow_cny=_decimal(row["net_mf_amount"], "net_mf_amount") * Decimal("10000"),
            large_order_net_flow_cny=(
                _decimal(row["buy_lg_amount"], "buy_lg_amount")
                - _decimal(row["sell_lg_amount"], "sell_lg_amount")
                + _decimal(row["buy_elg_amount"], "buy_elg_amount")
                - _decimal(row["sell_elg_amount"], "sell_elg_amount")
            )
            * Decimal("10000"),
            source=self.name,
        )

    @staticmethod
    def _require_a_share(instrument: Instrument) -> None:
        if instrument.market is not Market.A_SHARE:
            raise TushareResearchProviderError("Tushare research adapter only supports A-share")


def _parse_date(value: object, field: str) -> date:
    raw = str(value)
    try:
        return date.fromisoformat(f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}")
    except ValueError as error:
        raise TushareResearchProviderError(f"invalid {field}: {value!r}") from error


def _optional_decimal(value: object, field: str) -> Decimal | None:
    if value is None or str(value).lower() in {"", "nan", "none"}:
        return None
    return _decimal(value, field)


def _decimal(value: object, field: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except Exception as error:
        raise TushareResearchProviderError(f"invalid {field}: {value!r}") from error
    if not parsed.is_finite():
        raise TushareResearchProviderError(f"invalid {field}: {value!r}")
    return parsed
