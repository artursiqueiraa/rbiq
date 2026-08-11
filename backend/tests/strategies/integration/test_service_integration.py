from app.data.types import Timeframe
from app.strategies.service import StrategyService
from app.strategies.types import SignalDirection
from tests.strategies.conftest import STRONG_BULLISH_TREND
from tests.strategies.integration.conftest import BASE_TS, TEST_SYMBOL_PREFIX, seed_candles

SYMBOL = f"{TEST_SYMBOL_PREFIX}STRAT_SVC"


def test_full_pipeline_postgres_to_signal(db_session):
    """PostgreSQL -> CandleRepository -> MarketService -> MarketSnapshot ->
    StrategyService -> Strategy -> Signal, against the real database."""
    candles = seed_candles(db_session, SYMBOL, STRONG_BULLISH_TREND)

    service = StrategyService(db_session)
    evaluation = service.evaluate(
        strategy_name="trend_following", symbol=SYMBOL, timeframe=Timeframe.M1, timestamp=candles[-1].timestamp
    )

    assert evaluation.signal is not None
    assert evaluation.signal.direction == SignalDirection.CALL
    assert evaluation.signal.symbol == SYMBOL


def test_evaluate_all_runs_every_strategy_over_the_same_snapshot(db_session):
    candles = seed_candles(db_session, SYMBOL, STRONG_BULLISH_TREND)

    service = StrategyService(db_session)
    results = service.evaluate_all(symbol=SYMBOL, timeframe=Timeframe.M1, timestamp=candles[-1].timestamp)

    assert set(results.keys()) == {
        "trend_following",
        "pullback",
        "breakout",
        "mean_reversion",
        "price_action",
        "divergence",
    }
    assert results["trend_following"].signal.direction == SignalDirection.CALL
    assert results["price_action"].signal.direction == SignalDirection.CALL


def test_unknown_strategy_name_raises_value_error(db_session):
    candles = seed_candles(db_session, SYMBOL, STRONG_BULLISH_TREND[:10])
    service = StrategyService(db_session)
    try:
        service.evaluate(strategy_name="not_real", symbol=SYMBOL, timeframe=Timeframe.M1, timestamp=candles[-1].timestamp)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_empty_symbol_gives_no_signal_not_an_error(db_session):
    service = StrategyService(db_session)
    evaluation = service.evaluate(
        strategy_name="trend_following",
        symbol=f"{TEST_SYMBOL_PREFIX}DOES_NOT_EXIST",
        timeframe=Timeframe.M1,
        timestamp=BASE_TS,
    )
    assert evaluation.signal is None
