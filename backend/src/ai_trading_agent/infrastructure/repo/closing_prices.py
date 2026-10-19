"""One latest completed history window per instrument; never stores credentials."""

from datetime import date
from decimal import Decimal

from sqlalchemy.dialects.postgresql import insert

from ai_trading_agent.domain.ability.closing_prices import ClosingPrices
from ai_trading_agent.domain.aggregate.technical import PriceBar
from ai_trading_agent.infrastructure.repo.models import ClosingPriceCacheRecord as Record


class SqlAlchemyClosingPriceRepository:
    def __init__(self, sessions):
        self._sessions = sessions

    async def get(self, instrument):
        async with self._sessions() as session:
            record = await session.get(
                Record,
                (
                    instrument.symbol,
                    instrument.market.value,
                    instrument.instrument_type.value,
                    instrument.currency,
                ),
            )
            if record is None:
                return None
            bars = tuple(
                PriceBar(
                    instrument,
                    date.fromisoformat(row["date"]),
                    *(Decimal(row[key]) for key in ("open", "high", "low", "close", "volume")),
                )
                for row in record.bars
            )
            return ClosingPrices(instrument, record.source, record.fetched_at, bars)

    async def save(self, snapshot):
        if not snapshot.bars:
            return
        instrument = snapshot.instrument
        bars = sorted(snapshot.bars, key=lambda bar: bar.session_date)[-90:]
        statement = insert(Record).values(
            symbol=instrument.symbol,
            market=instrument.market.value,
            instrument_type=instrument.instrument_type.value,
            currency=instrument.currency,
            session_date=bars[-1].session_date,
            fetched_at=snapshot.fetched_at,
            source=snapshot.source,
            bars=[
                dict(
                    date=b.session_date.isoformat(),
                    open=str(b.open_price),
                    high=str(b.high_price),
                    low=str(b.low_price),
                    close=str(b.close_price),
                    volume=str(b.volume),
                )
                for b in bars
            ],
        )
        statement = statement.on_conflict_do_update(
            index_elements=[Record.symbol, Record.market, Record.instrument_type, Record.currency],
            set_={
                key: getattr(statement.excluded, key)
                for key in ("session_date", "fetched_at", "source", "bars")
            },
            where=(Record.session_date <= statement.excluded.session_date)
            & (Record.fetched_at <= statement.excluded.fetched_at),
        )
        async with self._sessions() as session:
            await session.execute(statement)
            await session.commit()
