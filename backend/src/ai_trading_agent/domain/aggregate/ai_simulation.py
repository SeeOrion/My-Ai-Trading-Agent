"""Auditable autonomous paper-trading aggregates; never broker orders."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.service.position_metrics import calculate_position_metrics


@dataclass(frozen=True, slots=True)
class AiSimulationPortfolio:
    portfolio_id: UUID
    market: str
    currency: str
    initial_capital: Decimal
    cash_balance: Decimal
    max_positions: int
    strategy_id: UUID | None = None
    status: str = "active"

    def __post_init__(self) -> None:
        if self.initial_capital <= 0 or self.cash_balance < 0:
            raise ValueError("simulation capital values are invalid")
        if not 1 <= self.max_positions <= 10:
            raise ValueError("max_positions must be between 1 and 10")
        if self.status not in {"active", "archived"}:
            raise ValueError("invalid simulation portfolio status")
        object.__setattr__(self, "market", self.market.strip())
        object.__setattr__(self, "currency", self.currency.strip().upper())


@dataclass(frozen=True, slots=True)
class AiSimulationPosition:
    position_id: UUID
    portfolio_id: UUID
    instrument: Instrument
    quantity: Decimal
    average_cost: Decimal
    opened_at: datetime
    candidate_score: Decimal
    factor_context: tuple[str, ...]
    rationale: tuple[str, ...]
    status: str = "open"

    def __post_init__(self) -> None:
        if self.quantity <= 0 or self.average_cost <= 0:
            raise ValueError("simulation position quantity and average_cost must be positive")
        if not Decimal("0") <= self.candidate_score <= Decimal("100"):
            raise ValueError("candidate_score must be between 0 and 100")
        if not self.factor_context or not self.rationale:
            raise ValueError("simulation position requires an auditable rationale")
        if self.status not in {"open", "closed"}:
            raise ValueError("invalid simulation position status")
        if self.opened_at.tzinfo is None:
            raise ValueError("opened_at must be timezone-aware")
        object.__setattr__(self, "opened_at", self.opened_at.astimezone(UTC))

    @property
    def cost_amount(self) -> Decimal:
        return calculate_position_metrics(self.quantity, self.average_cost).cost_amount


@dataclass(frozen=True, slots=True)
class AiSimulationTrade:
    trade_id: UUID
    portfolio_id: UUID
    position_id: UUID | None
    side: str
    quantity: Decimal
    price: Decimal
    executed_at: datetime
    rationale: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.side not in {"buy", "sell"}:
            raise ValueError("simulation side must be buy or sell")
        if self.quantity <= 0 or self.price <= 0:
            raise ValueError("simulation trade values must be positive")
        if self.executed_at.tzinfo is None:
            raise ValueError("executed_at must be timezone-aware")
        object.__setattr__(self, "executed_at", self.executed_at.astimezone(UTC))

    @property
    def amount(self) -> Decimal:
        return self.quantity * self.price


@dataclass(frozen=True, slots=True)
class AiSimulationPositionValuation:
    position: AiSimulationPosition
    display_name: str | None
    last_price: Decimal | None
    market_value: Decimal | None
    unrealized_pnl: Decimal | None
    unrealized_pnl_percent: Decimal | None
    daily_pnl: Decimal | None
    month_to_date_pnl: Decimal | None
    source: str | None


@dataclass(frozen=True, slots=True)
class AiSimulationDecisionReport:
    """A candidate-level explanation for a simulated buy or a skipped entry."""

    symbol: str
    display_name: str | None
    score: Decimal
    decision: str
    supportive_factor_count: int
    adverse_factor_count: int
    available_factor_ids: tuple[str, ...]
    unavailable_factor_ids: tuple[str, ...]
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.decision not in {"buy", "skip", "already_held"}:
            raise ValueError("invalid simulation decision")
        if self.supportive_factor_count < 0 or self.adverse_factor_count < 0:
            raise ValueError("factor counts must not be negative")
        if self.decision == "skip" and not self.blockers:
            raise ValueError("skipped simulation candidates require blockers")


@dataclass(frozen=True, slots=True)
class AiSimulationOverview:
    portfolio: AiSimulationPortfolio
    observed_at: datetime
    positions: tuple[AiSimulationPositionValuation, ...]
    invested_cost: Decimal
    market_value: Decimal
    total_equity: Decimal
    cumulative_pnl: Decimal
    daily_pnl: Decimal | None
    month_to_date_pnl: Decimal | None
    notices: tuple[str, ...] = ()
    decision_reports: tuple[AiSimulationDecisionReport, ...] = ()

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("overview observation must be timezone-aware")
        object.__setattr__(self, "observed_at", self.observed_at.astimezone(UTC))
