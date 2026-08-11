from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.data.types import Timeframe
from app.market.snapshot import MarketParams, build_snapshot
from app.market.structure.structure_engine import StructureAnalysis, analyze_structure
from app.market.structure.swings import detect_swings
from app.market.types import MarketSnapshot
from app.repositories.candle_repository import CandleRepository

EARLIEST_DEFAULT = datetime(1970, 1, 1, tzinfo=timezone.utc)


class MarketService:
    """The only thing between the API and the Market Engine: fetches candles
    up to the requested point in time (never beyond it — that's what keeps the
    whole engine causal) and hands them to the pure `build_snapshot`."""

    def __init__(self, session: Session):
        self.candles = CandleRepository(session)

    def get_snapshot(
        self,
        *,
        symbol: str,
        timeframe: Timeframe,
        timestamp: datetime,
        params: MarketParams = MarketParams(),
    ) -> MarketSnapshot:
        candles = self.candles.get_domain(symbol, timeframe, EARLIEST_DEFAULT, timestamp)
        return build_snapshot(candles, symbol=symbol, timeframe=timeframe, params=params)

    def get_structure_history(
        self,
        *,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
        params: MarketParams = MarketParams(),
    ) -> StructureAnalysis:
        candles = self.candles.get_domain(symbol, timeframe, start, end)
        swings = detect_swings(candles, left_bars=params.left_bars, right_bars=params.right_bars)
        return analyze_structure(candles, swings)
