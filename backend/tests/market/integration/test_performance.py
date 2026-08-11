import time
from datetime import timedelta

from app.data.types import Timeframe
from app.market.snapshot import build_snapshot
from tests.market.integration.conftest import BASE_TS, TEST_SYMBOL_PREFIX, seed_candles

SYMBOL = f"{TEST_SYMBOL_PREFIX}MARKET_PERF"
CANDLE_COUNT = 100_000


def _zigzag_closes(n: int) -> list[float]:
    """A steady zigzag with a slow upward drift, so there are plenty of real
    swings (not just one giant trend) for the structure/S-R detection to work
    through — closer to what the engine will actually see in practice than a
    monotonic ramp."""
    closes = []
    price = 100.0
    direction = 1
    for i in range(n):
        price += direction * 0.5 + 0.001  # slow upward drift
        if i % 6 == 0:
            direction *= -1
        closes.append(round(price, 4))
    return closes


def test_builds_market_snapshot_over_100k_candles(db_session):
    """Not a hard performance gate (per Sprint 4 scope) — measures and records
    Market Structure + Support/Resistance + Market Regime + Market Snapshot
    over 100k candles fetched from the real PostgreSQL, same style as the
    Sprint 2/3 performance tests."""
    closes = _zigzag_closes(CANDLE_COUNT)
    candles = seed_candles(db_session, SYMBOL, closes)

    from app.repositories.candle_repository import CandleRepository

    started_fetch = time.perf_counter()
    fetched = CandleRepository(db_session).get_domain(
        SYMBOL, Timeframe.M1, BASE_TS, BASE_TS + timedelta(minutes=CANDLE_COUNT)
    )
    fetch_elapsed = time.perf_counter() - started_fetch
    assert len(fetched) == CANDLE_COUNT

    started_snapshot = time.perf_counter()
    snapshot = build_snapshot(fetched, symbol=SYMBOL, timeframe=Timeframe.M1)
    snapshot_elapsed = time.perf_counter() - started_snapshot

    print(
        f"\n[performance] {CANDLE_COUNT} candles | fetch from Postgres: {fetch_elapsed:.2f}s | "
        f"swings + structure + S/R + regime + snapshot: {snapshot_elapsed:.2f}s | "
        f"swing highs: {len([e for e in snapshot.structure_events if 'HIGH' in e.event_type.value])}"
    )

    assert snapshot.structure_state is not None

    # Generous ceiling: a bottleneck smoke test, not a benchmark to optimize for.
    assert fetch_elapsed < 60
    assert snapshot_elapsed < 60
