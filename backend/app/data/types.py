from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum


class Timeframe(str, Enum):
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"

    @property
    def duration(self) -> timedelta:
        return _TIMEFRAME_DURATIONS[self]


_TIMEFRAME_DURATIONS: dict[Timeframe, timedelta] = {
    Timeframe.M1: timedelta(minutes=1),
    Timeframe.M5: timedelta(minutes=5),
    Timeframe.M15: timedelta(minutes=15),
    Timeframe.M30: timedelta(minutes=30),
    Timeframe.H1: timedelta(hours=1),
    Timeframe.H4: timedelta(hours=4),
    Timeframe.D1: timedelta(days=1),
}


class DataSource(str, Enum):
    CSV = "CSV"
    PARQUET = "PARQUET"
    IQ_OPTION = "IQ_OPTION"
    OTHER = "OTHER"


@dataclass(frozen=True)
class Asset:
    symbol: str
    name: str
    market: str


@dataclass(frozen=True)
class Candle:
    """Canonical candle shape. Prices use Decimal to avoid float rounding drift.

    Construction does not itself enforce a UTC-aware timestamp: the Normalizer
    produces these before validation runs, and the Validator is what flags a
    naive timestamp as an issue. Anything persisted to the database or trusted
    by downstream engines must have passed through app.data.validation first.
    """

    symbol: str
    timeframe: Timeframe
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    source: DataSource
    volume: Decimal | None = None
