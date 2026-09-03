"""Strict, declarative factor definitions and point-in-time diagnostics."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from math import sqrt
from re import compile

from ai_trading_agent.domain.aggregate.market import Instrument

_FACTOR_ID = compile(r"^[a-z][a-z0-9_]{2,63}$")
_PRICE_COLUMNS = frozenset({"open", "high", "low", "close", "volume", "turnover"})


@dataclass(frozen=True, slots=True)
class FactorMetadata:
    """A reviewable factor contract. Formulas are documentation, never executable code."""

    identifier: str
    name: str
    theme: str
    formula: str
    columns_required: tuple[str, ...]
    warmup_bars: int
    horizon_days: int
    description: str
    version: str = "1.0.0"

    def __post_init__(self) -> None:
        if not _FACTOR_ID.fullmatch(self.identifier):
            raise ValueError("identifier must be snake_case and at least 3 characters")
        text_fields = (self.name, self.theme, self.formula, self.description)
        if not all(value.strip() for value in text_fields):
            raise ValueError("factor metadata text fields must not be empty")
        if not self.columns_required:
            raise ValueError("columns_required must not be empty")
        unknown = set(self.columns_required) - _PRICE_COLUMNS
        invalid_fundamentals = {column for column in unknown if not column.startswith("fund:")}
        if invalid_fundamentals:
            raise ValueError(f"unsupported input columns: {sorted(invalid_fundamentals)}")
        if self.warmup_bars < 0 or self.horizon_days < 1:
            raise ValueError("warmup_bars must be non-negative and horizon_days must be positive")


class FactorRegistry:
    """In-memory registry; persistence is an infrastructure concern."""

    def __init__(self, definitions: tuple[FactorMetadata, ...] = ()) -> None:
        self._definitions: dict[str, FactorMetadata] = {}
        for definition in definitions:
            self.register(definition)

    def register(self, definition: FactorMetadata) -> None:
        if definition.identifier in self._definitions:
            raise ValueError(f"factor already registered: {definition.identifier}")
        self._definitions[definition.identifier] = definition

    def get(self, identifier: str) -> FactorMetadata:
        try:
            return self._definitions[identifier]
        except KeyError as error:
            raise KeyError(f"unknown factor: {identifier}") from error

    def list(self) -> tuple[FactorMetadata, ...]:
        return tuple(sorted(self._definitions.values(), key=lambda item: item.identifier))


@dataclass(frozen=True, slots=True)
class FactorReturnPair:
    """A factor observation paired only with a return realized after its as-of date."""

    instrument: Instrument
    as_of: date
    realized_for: date
    factor_value: Decimal
    realized_return: Decimal

    def __post_init__(self) -> None:
        if self.realized_for <= self.as_of:
            raise ValueError("realized_for must be after as_of to avoid look-ahead bias")


@dataclass(frozen=True, slots=True)
class FactorDiagnostics:
    observations: int
    daily_ic: tuple[tuple[date, Decimal], ...]
    information_coefficient: Decimal | None
    information_ratio: Decimal | None


def calculate_factor_diagnostics(pairs: tuple[FactorReturnPair, ...]) -> FactorDiagnostics:
    """Calculate date-wise Spearman IC, excluding cross-sections under five names."""
    by_date: dict[date, list[FactorReturnPair]] = defaultdict(list)
    for pair in pairs:
        by_date[pair.as_of].append(pair)

    daily: list[tuple[date, Decimal]] = []
    for as_of, entries in sorted(by_date.items()):
        if len(entries) < 5:
            continue
        ic = _spearman(
            [entry.factor_value for entry in entries],
            [entry.realized_return for entry in entries],
        )
        daily.append((as_of, ic))
    values = [item[1] for item in daily]
    if not values:
        return FactorDiagnostics(len(pairs), tuple(), None, None)
    mean = sum(values, start=Decimal("0")) / Decimal(len(values))
    if len(values) < 2:
        return FactorDiagnostics(len(pairs), tuple(daily), mean, None)
    variance = sum(((value - mean) ** 2 for value in values), start=Decimal("0")) / Decimal(
        len(values) - 1
    )
    std = Decimal(str(sqrt(float(variance))))
    information_ratio = None if std == 0 else mean / std
    return FactorDiagnostics(len(pairs), tuple(daily), mean, information_ratio)


def _spearman(left: list[Decimal], right: list[Decimal]) -> Decimal:
    left_rank = _average_ranks(left)
    right_rank = _average_ranks(right)
    count = Decimal(len(left_rank))
    left_mean = sum(left_rank, start=Decimal("0")) / count
    right_mean = sum(right_rank, start=Decimal("0")) / count
    numerator = sum(
        ((x - left_mean) * (y - right_mean) for x, y in zip(left_rank, right_rank, strict=True)),
        start=Decimal("0"),
    )
    left_scale = sum(((x - left_mean) ** 2 for x in left_rank), start=Decimal("0"))
    right_scale = sum(((y - right_mean) ** 2 for y in right_rank), start=Decimal("0"))
    denominator = Decimal(str(sqrt(float(left_scale * right_scale))))
    return Decimal("0") if denominator == 0 else numerator / denominator


def _average_ranks(values: list[Decimal]) -> list[Decimal]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [Decimal("0")] * len(values)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and ordered[end][1] == ordered[start][1]:
            end += 1
        average = Decimal(start + 1 + end) / Decimal("2")
        for index, _ in ordered[start:end]:
            ranks[index] = average
        start = end
    return ranks


DEFAULT_FACTOR_REGISTRY = FactorRegistry(
    (
        FactorMetadata(
            "momentum_20d", "20日动量", "momentum", "close[t] / close[t-20] - 1",
            ("close",), 20, 20, "过去二十个交易日的价格动量。",
        ),
        FactorMetadata(
            "volatility_20d", "20日波动率", "risk", "std(returns, 20)",
            ("close",), 21, 20, "过去二十个交易日收益率的波动风险。",
        ),
        FactorMetadata(
            "earnings_yield", "盈利收益率", "value", "1 / fund:pe_ttm",
            ("fund:pe_ttm",), 0, 60, "市盈率倒数；非正市盈率应保持缺失值。",
        ),
        FactorMetadata(
            "return_on_equity", "净资产收益率", "quality", "fund:roe_pct",
            ("fund:roe_pct",), 0, 60, "使用已公告财报中的 ROE，按公告日对齐。",
        ),
        FactorMetadata(
            "news_sentiment", "新闻情绪", "sentiment", "mean(article_sentiment, 1d)",
            ("fund:news_sentiment",), 0, 5, "已采集财经新闻的可解释情绪均值。",
        ),
    )
)
