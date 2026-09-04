"""SQLAlchemy records for auditable, private-server PostgreSQL storage."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

SCHEMA = "trading_agent"


class Base(DeclarativeBase):
    pass


class TimestampedRecord:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class FactorDefinitionRecord(Base, TimestampedRecord):
    __tablename__ = "factor_definitions"
    __table_args__ = {"schema": SCHEMA}

    identifier: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    theme: Mapped[str] = mapped_column(String(64), nullable=False)
    formula: Mapped[str] = mapped_column(Text, nullable=False)
    columns_required: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    warmup_bars: Mapped[int] = mapped_column(Integer, nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class StrategyProfileRecord(Base, TimestampedRecord):
    __tablename__ = "strategy_profiles"
    __table_args__ = {"schema": SCHEMA}

    strategy_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    definition: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class TradingDisciplineRecord(Base, TimestampedRecord):
    __tablename__ = "trading_disciplines"
    __table_args__ = {"schema": SCHEMA}

    discipline_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    market: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    definition: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class DocumentRecord(Base, TimestampedRecord):
    __tablename__ = "documents"
    __table_args__ = {"schema": SCHEMA}

    document_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(128), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    extraction_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    extracted_text: Mapped[str | None] = mapped_column(Text)


class TradeJournalRecord(Base, TimestampedRecord):
    __tablename__ = "trade_journal_records"
    __table_args__ = {"schema": SCHEMA}

    record_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    traded_on: Mapped[date] = mapped_column(Date, nullable=False)
    market: Mapped[str] = mapped_column(String(32), nullable=False)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[str] = mapped_column(String(64), nullable=False)
    price: Mapped[str] = mapped_column(String(64), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    fees: Mapped[str] = mapped_column(String(64), nullable=False, default="0")
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    note: Mapped[str | None] = mapped_column(Text)


class StrategyRunRecord(Base, TimestampedRecord):
    __tablename__ = "strategy_runs"
    __table_args__ = {"schema": SCHEMA}

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    strategy_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.strategy_profiles.strategy_id"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON)
