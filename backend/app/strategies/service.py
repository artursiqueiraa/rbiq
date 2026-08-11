from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.data.types import Timeframe
from app.indicators.registry import IndicatorRegistry, result_key
from app.indicators.types import IndicatorResult
from app.market.service import MarketService
from app.market.types import MarketSnapshot
from app.repositories.candle_repository import CandleRepository
from app.strategies.base import Strategy
from app.strategies.context import StrategyContext
from app.strategies.registry import StrategyRegistry
from app.strategies.types import StrategyEvaluation

EARLIEST_DEFAULT = datetime(1970, 1, 1, tzinfo=timezone.utc)


class StrategyService:
    """The only thing between the API and the Strategy Engine: builds a
    causally-bounded StrategyContext (candles and market snapshot never see
    past `timestamp`) and hands it to a Strategy. Never touches SQL beyond
    what CandleRepository/MarketService already expose, never talks to a
    broker."""

    def __init__(self, session: Session):
        self.session = session
        self.candles = CandleRepository(session)
        self.market = MarketService(session)

    def _indicators_for(self, strategy: Strategy, candles) -> dict[str, IndicatorResult]:
        indicators: dict[str, IndicatorResult] = {}
        for spec in strategy.required_indicators():
            indicator = IndicatorRegistry.create(spec.name, **spec.parameters)
            result = indicator.calculate(candles)
            indicators[result_key(result)] = result
        return indicators

    def _build_context(
        self,
        *,
        symbol: str,
        timeframe: Timeframe,
        timestamp: datetime,
        snapshot: MarketSnapshot,
        candles,
        strategy: Strategy,
    ) -> StrategyContext:
        return StrategyContext(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=timestamp,
            market_snapshot=snapshot,
            candles=candles,
            indicators=self._indicators_for(strategy, candles),
        )

    def evaluate(
        self,
        *,
        strategy_name: str,
        symbol: str,
        timeframe: Timeframe,
        timestamp: datetime,
        parameters: dict | None = None,
    ) -> StrategyEvaluation:
        strategy = StrategyRegistry.create(strategy_name, **(parameters or {}))
        snapshot = self.market.get_snapshot(symbol=symbol, timeframe=timeframe, timestamp=timestamp)
        candles = self.candles.get_domain(symbol, timeframe, EARLIEST_DEFAULT, timestamp)
        context = self._build_context(
            symbol=symbol, timeframe=timeframe, timestamp=timestamp, snapshot=snapshot, candles=candles, strategy=strategy
        )
        strategy.prepare(context)
        return strategy.evaluate(context)

    def evaluate_all(
        self,
        *,
        symbol: str,
        timeframe: Timeframe,
        timestamp: datetime,
    ) -> dict[str, StrategyEvaluation]:
        """Runs every registered strategy over the SAME market snapshot and
        candle set — fetched once, not once per strategy — so results are
        directly comparable and the database isn't hit six times for
        identical data."""
        snapshot = self.market.get_snapshot(symbol=symbol, timeframe=timeframe, timestamp=timestamp)
        candles = self.candles.get_domain(symbol, timeframe, EARLIEST_DEFAULT, timestamp)

        results: dict[str, StrategyEvaluation] = {}
        for name in StrategyRegistry.names():
            strategy = StrategyRegistry.create(name)
            context = self._build_context(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=timestamp,
                snapshot=snapshot,
                candles=candles,
                strategy=strategy,
            )
            strategy.prepare(context)
            results[name] = strategy.evaluate(context)
        return results
