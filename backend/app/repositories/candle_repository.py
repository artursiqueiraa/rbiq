from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.data.quality import DataQualityReport, compute_quality_report
from app.data.types import Candle, Timeframe
from app.database.models import CandleModel


def _timeframe_value(timeframe: Timeframe | str) -> str:
    return timeframe.value if isinstance(timeframe, Timeframe) else timeframe


BATCH_SIZE = 5000


class CandleRepository:
    """All persistence for candles goes through here — routes and services never
    issue SQL directly against the candles table."""

    def __init__(self, session: Session):
        self.session = session

    def bulk_insert(self, candles: list[Candle], *, batch_size: int = BATCH_SIZE) -> int:
        """Idempotent insert: re-running with the same candles inserts nothing new
        (ON CONFLICT on the (symbol, timeframe, timestamp) unique constraint covers
        both rows that already exist in the table and duplicates within the same
        batch). Processed in chunks so a 100k-row import isn't one giant statement.
        Returns how many rows were actually new."""
        total_inserted = 0

        for offset in range(0, len(candles), batch_size):
            chunk = candles[offset : offset + batch_size]
            rows = [
                {
                    "symbol": c.symbol,
                    "timeframe": _timeframe_value(c.timeframe),
                    "timestamp": c.timestamp,
                    "open": c.open,
                    "high": c.high,
                    "low": c.low,
                    "close": c.close,
                    "volume": c.volume,
                    "source": c.source.value,
                }
                for c in chunk
            ]

            stmt = (
                pg_insert(CandleModel)
                .values(rows)
                .on_conflict_do_nothing(index_elements=["symbol", "timeframe", "timestamp"])
                .returning(CandleModel.id)
            )
            inserted_ids = self.session.execute(stmt).scalars().all()
            total_inserted += len(inserted_ids)

        self.session.commit()
        return total_inserted

    def get(
        self,
        symbol: str,
        timeframe: Timeframe | str,
        start: datetime,
        end: datetime,
    ) -> list[CandleModel]:
        stmt = (
            select(CandleModel)
            .where(
                CandleModel.symbol == symbol,
                CandleModel.timeframe == _timeframe_value(timeframe),
                CandleModel.timestamp >= start,
                CandleModel.timestamp <= end,
            )
            .order_by(CandleModel.timestamp.asc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def count(self, symbol: str | None = None, timeframe: Timeframe | str | None = None) -> int:
        stmt = select(func.count()).select_from(CandleModel)
        if symbol is not None:
            stmt = stmt.where(CandleModel.symbol == symbol)
        if timeframe is not None:
            stmt = stmt.where(CandleModel.timeframe == _timeframe_value(timeframe))
        return self.session.execute(stmt).scalar_one()

    def exists(self, symbol: str, timeframe: Timeframe | str, timestamp: datetime) -> bool:
        stmt = (
            select(CandleModel.id)
            .where(
                CandleModel.symbol == symbol,
                CandleModel.timeframe == _timeframe_value(timeframe),
                CandleModel.timestamp == timestamp,
            )
            .limit(1)
        )
        return self.session.execute(stmt).first() is not None

    def get_quality(self, symbol: str, timeframe: Timeframe | str) -> DataQualityReport:
        stmt = (
            select(CandleModel)
            .where(
                CandleModel.symbol == symbol,
                CandleModel.timeframe == _timeframe_value(timeframe),
            )
            .order_by(CandleModel.timestamp.asc())
        )
        rows = self.session.execute(stmt).scalars().all()
        timestamps = [row.timestamp for row in rows]
        return compute_quality_report(timestamps, symbol=symbol, timeframe=_timeframe_value(timeframe))
