from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Timeframe(str, Enum):
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"


@dataclass(frozen=True)
class Asset:
    symbol: str
    name: str
    market: str


@dataclass(frozen=True)
class Candle:
    asset: str
    timeframe: Timeframe
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None
