"""Immutable output of a personal-discipline rule evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ai_trading_agent.domain.aggregate.discipline import TradingDiscipline
from ai_trading_agent.domain.enums.research import DisciplineDecisionStatus


@dataclass(frozen=True, slots=True)
class DisciplineDecision:
    """A reproducible state derived from one quote and one saved discipline."""

    discipline: TradingDiscipline
    status: DisciplineDecisionStatus
    last_price: Decimal
    matched_level: Decimal | None
