"""Declarative personal trading disciplines; never instructions to execute orders."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.enums.research import DisciplineStatus


@dataclass(frozen=True, slots=True)
class TradingDiscipline:
    """A price-based plan the user may review before making a manual decision."""

    discipline_id: UUID
    name: str
    instrument: Instrument
    buy_price: Decimal
    add_price: Decimal | None
    take_profit_price: Decimal
    exit_price: Decimal
    notes: str = ""
    status: DisciplineStatus = DisciplineStatus.ACTIVE
    version: int = 1

    def __post_init__(self) -> None:
        if not self.name.strip() or len(self.name) > 160:
            raise ValueError("name must contain 1 to 160 characters")
        if len(self.notes) > 4_000:
            raise ValueError("notes must contain at most 4000 characters")
        if self.version < 1:
            raise ValueError("version must be positive")
        prices = (self.buy_price, self.take_profit_price, self.exit_price)
        if self.add_price is not None:
            prices += (self.add_price,)
        if any(price <= Decimal("0") for price in prices):
            raise ValueError("discipline prices must be positive")
        if not self.exit_price < self.buy_price < self.take_profit_price:
            raise ValueError(
                "exit_price must be below buy_price and take_profit_price above buy_price"
            )
        if (
            self.add_price is not None
            and not self.buy_price < self.add_price < self.take_profit_price
        ):
            raise ValueError("add_price must be between buy_price and take_profit_price")

    def definition(self) -> dict[str, object]:
        return {
            "instrument_type": self.instrument.instrument_type.value,
            "buy_price": str(self.buy_price),
            "add_price": None if self.add_price is None else str(self.add_price),
            "take_profit_price": str(self.take_profit_price),
            "exit_price": str(self.exit_price),
            "notes": self.notes,
        }

    @classmethod
    def from_record(
        cls,
        *,
        discipline_id: str,
        name: str,
        symbol: str,
        market: str,
        status: str,
        version: int,
        definition: dict[str, object],
    ) -> TradingDiscipline:
        from ai_trading_agent.domain.enums.market import InstrumentType, Market

        raw_add_price = definition.get("add_price")
        return cls(
            discipline_id=UUID(discipline_id),
            name=name,
            instrument=Instrument(
                symbol,
                Market(market),
                InstrumentType(str(definition.get("instrument_type", "equity"))),
            ),
            buy_price=Decimal(str(definition["buy_price"])),
            add_price=None if raw_add_price is None else Decimal(str(raw_add_price)),
            take_profit_price=Decimal(str(definition["take_profit_price"])),
            exit_price=Decimal(str(definition["exit_price"])),
            notes=str(definition.get("notes", "")),
            status=DisciplineStatus(status),
            version=version,
        )
