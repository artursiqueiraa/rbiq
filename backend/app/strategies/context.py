from dataclasses import dataclass
from datetime import datetime

from app.data.types import Candle, Timeframe
from app.indicators.types import IndicatorResult
from app.market.types import MarketSnapshot


@dataclass(frozen=True)
class StrategyContext:
    """Everything a Strategy is allowed to see. Deliberately excludes broker,
    account, balance, order, and execution concerns (Sprint 5 section 6) — a
    Strategy that needs something not listed here is asking for the wrong
    thing.

    `candles` and `market_snapshot` are both already causally bounded to
    `timestamp` by StrategyService before this object is built — a Strategy
    itself never needs to worry about look-ahead as long as it only reads
    from this context.
    """

    symbol: str
    timeframe: Timeframe
    timestamp: datetime
    market_snapshot: MarketSnapshot
    candles: list[Candle]
    indicators: dict[str, IndicatorResult]
