from datetime import timedelta
from decimal import Decimal

from app.data.types import Candle, DataSource, Timeframe
from app.repositories.candle_repository import CandleRepository
from app.strategies.service import StrategyService
from tests.strategies.conftest import STRONG_BULLISH_TREND
from tests.strategies.integration.conftest import BASE_TS, TEST_SYMBOL_PREFIX

SYMBOL = f"{TEST_SYMBOL_PREFIX}STRAT_LA"

# Split point chosen so both halves are non-trivial and the first half alone
# still has enough history for every strategy's default indicators.
SPLIT = 60


def _make_candles(symbol: str, closes: list[float], start_index: int) -> list[Candle]:
    return [
        Candle(
            symbol=symbol,
            timeframe=Timeframe.M1,
            timestamp=BASE_TS + timedelta(minutes=start_index + i),
            open=Decimal(str(c)),
            high=Decimal(str(c + 0.5)),
            low=Decimal(str(c - 0.5)),
            close=Decimal(str(c)),
            volume=None,
            source=DataSource.CSV,
        )
        for i, c in enumerate(closes)
    ]


def test_signal_at_t_is_unchanged_after_future_candles_are_inserted(db_session):
    """Section 58, the mandatory per-strategy look-ahead test, proven the only
    way it can actually mean something: `Strategy.evaluate()` never sees more
    than whatever StrategyContext hands it, so the real guarantee lives in
    StrategyService + CandleRepository bounding candles by `timestamp`. This
    proves that guarantee end to end against the real database, for all six
    strategies at once (evaluate_all): insert data up to T, evaluate at T,
    THEN insert T+1..T+N, evaluate at T again, and require an identical
    result for every strategy.
    """
    repo = CandleRepository(db_session)

    first_candles = _make_candles(SYMBOL, STRONG_BULLISH_TREND[:SPLIT], 0)
    repo.bulk_insert(first_candles)
    t = first_candles[-1].timestamp

    service = StrategyService(db_session)
    before = service.evaluate_all(symbol=SYMBOL, timeframe=Timeframe.M1, timestamp=t)

    second_candles = _make_candles(SYMBOL, STRONG_BULLISH_TREND[SPLIT:], SPLIT)
    repo.bulk_insert(second_candles)

    after = service.evaluate_all(symbol=SYMBOL, timeframe=Timeframe.M1, timestamp=t)

    for name in before:
        assert before[name].signal == after[name].signal, f"{name}: signal at T changed after future candles were inserted"
        assert before[name].triggered_conditions == after[name].triggered_conditions
        assert before[name].failed_conditions == after[name].failed_conditions
