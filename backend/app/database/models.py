from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base

# NUMERIC(18, 8): enough range for FX/crypto-style prices with 8 decimal places of
# precision, and explicit rather than letting the driver pick a float column.
PRICE = Numeric(18, 8)


class CandleModel(Base):
    __tablename__ = "candles"
    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "timestamp", name="uq_candles_symbol_timeframe_timestamp"),
        Index("ix_candles_symbol_timeframe_timestamp", "symbol", "timeframe", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(4), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    high: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    low: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    close: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    volume: Mapped[Decimal | None] = mapped_column(PRICE, nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DataImportModel(Base):
    __tablename__ = "data_imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    source_file: Mapped[str] = mapped_column(String(500), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(4), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gaps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[str | None] = mapped_column(String, nullable=True)


__all__ = ["Base", "CandleModel", "DataImportModel"]
