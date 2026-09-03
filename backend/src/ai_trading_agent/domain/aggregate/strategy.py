"""Personal strategy profiles are declarative research preferences, never executable code."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from ai_trading_agent.domain.enums.market import Market


@dataclass(frozen=True, slots=True)
class StrategyProfile:
    strategy_id: UUID
    name: str
    thesis: str
    factor_ids: tuple[str, ...]
    markets: tuple[Market, ...]
    max_position_pct: Decimal
    risk_notes: str
    status: str = "draft"
    version: int = 1

    def __post_init__(self) -> None:
        if not self.name.strip() or len(self.name) > 160:
            raise ValueError("name must contain 1 to 160 characters")
        if not self.thesis.strip() or len(self.thesis) > 8_000:
            raise ValueError("thesis must contain 1 to 8000 characters")
        if not self.factor_ids:
            raise ValueError("at least one factor is required")
        if len(set(self.factor_ids)) != len(self.factor_ids):
            raise ValueError("factor_ids must not contain duplicates")
        if not self.markets:
            raise ValueError("at least one market is required")
        if not Decimal("0") < self.max_position_pct <= Decimal("100"):
            raise ValueError("max_position_pct must be in (0, 100]")
        if self.status not in {"draft", "active", "archived"}:
            raise ValueError("status must be draft, active, or archived")
        if self.version < 1:
            raise ValueError("version must be positive")

    def definition(self) -> dict[str, object]:
        return {
            "thesis": self.thesis,
            "factor_ids": list(self.factor_ids),
            "markets": [market.value for market in self.markets],
            "max_position_pct": str(self.max_position_pct),
            "risk_notes": self.risk_notes,
        }

    @classmethod
    def from_record(
        cls,
        *,
        strategy_id: str,
        name: str,
        status: str,
        version: int,
        definition: dict[str, object],
    ) -> StrategyProfile:
        return cls(
            strategy_id=UUID(strategy_id),
            name=name,
            thesis=str(definition["thesis"]),
            factor_ids=tuple(str(item) for item in definition["factor_ids"]),
            markets=tuple(Market(str(item)) for item in definition["markets"]),
            max_position_pct=Decimal(str(definition["max_position_pct"])),
            risk_notes=str(definition.get("risk_notes", "")),
            status=status,
            version=version,
        )
