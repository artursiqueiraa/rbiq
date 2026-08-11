import time
from datetime import timedelta

from app.data.types import Timeframe
from app.indicators import ATR, CCI, EMA, MACD, RSI, SMA, Bollinger, Stochastic, calculate_indicators
from tests.indicators.integration.conftest import BASE_TS, TEST_SYMBOL_PREFIX, seed_candles

SYMBOL = f"{TEST_SYMBOL_PREFIX}IND_PERF"
CANDLE_COUNT = 100_000


def test_calculates_all_eight_indicators_over_100k_candles(db_session):
    """Not a hard performance gate — Sprint 3 explicitly asks only to measure
    and record this, not to hit a target. Uses the real PostgreSQL to also
    cover fetching 100k rows through CandleRepository.get_domain, not just the
    in-memory math."""
    closes = [100 + (i % 137) * 0.37 for i in range(CANDLE_COUNT)]  # deterministic, non-trivial wiggle
    seed_candles(db_session, SYMBOL, closes)

    from app.repositories.candle_repository import CandleRepository

    started_fetch = time.perf_counter()
    candles = CandleRepository(db_session).get_domain(
        SYMBOL, Timeframe.M1, BASE_TS, BASE_TS + timedelta(minutes=CANDLE_COUNT)
    )
    fetch_elapsed = time.perf_counter() - started_fetch
    assert len(candles) == CANDLE_COUNT

    indicators = [
        SMA(period=20),
        EMA(period=20),
        RSI(period=14),
        MACD(),
        Bollinger(period=20),
        ATR(period=14),
        Stochastic(),
        CCI(period=20),
    ]

    started_calc = time.perf_counter()
    results = calculate_indicators(candles, indicators)
    calc_elapsed = time.perf_counter() - started_calc

    assert len(results) == 8

    print(
        f"\n[performance] {CANDLE_COUNT} candles | fetch from Postgres: {fetch_elapsed:.2f}s | "
        f"8 indicators calculated: {calc_elapsed:.2f}s"
    )

    # Generous ceiling: a bottleneck smoke test, not a benchmark to optimize for.
    assert fetch_elapsed < 60
    assert calc_elapsed < 60
