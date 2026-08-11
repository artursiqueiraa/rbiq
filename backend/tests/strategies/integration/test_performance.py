import time
from datetime import timedelta

from app.data.types import Timeframe
from app.market.service import MarketService
from app.strategies.registry import StrategyRegistry
from app.strategies.service import StrategyService
from tests.strategies.integration.conftest import BASE_TS, TEST_SYMBOL_PREFIX, seed_candles

SYMBOL = f"{TEST_SYMBOL_PREFIX}STRATEGY_PERF"
CANDLE_COUNT = 100_000


def _zigzag_closes(n: int) -> list[float]:
    closes = []
    price = 100.0
    direction = 1
    for i in range(n):
        price += direction * 0.5 + 0.001
        if i % 6 == 0:
            direction *= -1
        closes.append(round(price, 4))
    return closes


def test_evaluates_all_six_strategies_over_100k_candles(db_session):
    """Not a hard performance gate (per Sprint 5 scope) — measures and records
    per-strategy and total time over 100k candles fetched from the real
    PostgreSQL, same style as the Sprint 2-4 performance tests."""
    closes = _zigzag_closes(CANDLE_COUNT)
    candles = seed_candles(db_session, SYMBOL, closes)
    timestamp = candles[-1].timestamp

    market = MarketService(db_session)
    started_snapshot = time.perf_counter()
    market.get_snapshot(symbol=SYMBOL, timeframe=Timeframe.M1, timestamp=timestamp)
    snapshot_elapsed = time.perf_counter() - started_snapshot

    service = StrategyService(db_session)
    per_strategy: dict[str, float] = {}
    started_total = time.perf_counter()
    for name in StrategyRegistry.names():
        started = time.perf_counter()
        service.evaluate(strategy_name=name, symbol=SYMBOL, timeframe=Timeframe.M1, timestamp=timestamp)
        per_strategy[name] = time.perf_counter() - started
    total_elapsed = time.perf_counter() - started_total

    breakdown = " | ".join(f"{name}={elapsed:.2f}s" for name, elapsed in per_strategy.items())

    # For comparison: evaluate_all() fetches candles and the snapshot ONCE and
    # reuses them for all six strategies, instead of each evaluate() call
    # redoing its own DB fetch + full snapshot rebuild (swings, structure,
    # S/R, ATR, EMA) from scratch. This is the realistic path for anything
    # that wants multiple strategies' opinions on the same moment (e.g. the
    # Strategy Lab's "evaluate-all" comparison view).
    started_all = time.perf_counter()
    service.evaluate_all(symbol=SYMBOL, timeframe=Timeframe.M1, timestamp=timestamp)
    evaluate_all_elapsed = time.perf_counter() - started_all

    print(
        f"\n[performance] {CANDLE_COUNT} candles | snapshot: {snapshot_elapsed:.2f}s | "
        f"6x independent evaluate(): {total_elapsed:.2f}s | {breakdown} | "
        f"evaluate_all() (shared fetch): {evaluate_all_elapsed:.2f}s"
    )

    # Generous ceiling: a bottleneck smoke test, not a benchmark to optimize for.
    assert total_elapsed < 120
    assert evaluate_all_elapsed < 120
