from app.data.types import Timeframe
from app.market.snapshot import build_snapshot
from tests.market.conftest import BULLISH_CLOSES, make_candles


def test_snapshot_is_deterministic():
    candles = make_candles(BULLISH_CLOSES)

    first = build_snapshot(candles, symbol="X", timeframe=Timeframe.M1)
    second = build_snapshot(candles, symbol="X", timeframe=Timeframe.M1)

    assert first.structure_state == second.structure_state
    assert first.direction == second.direction
    assert first.regime == second.regime
    assert first.volatility == second.volatility
    assert first.volatility_value == second.volatility_value
    assert first.trend_strength == second.trend_strength
    assert first.latest_swing_high == second.latest_swing_high
    assert first.latest_swing_low == second.latest_swing_low
    assert first.supports == second.supports
    assert first.resistances == second.resistances
    assert first.structure_events == second.structure_events


def test_candles_are_not_mutated_by_snapshot_building():
    candles = make_candles(BULLISH_CLOSES)
    candles_before = list(candles)

    build_snapshot(candles, symbol="X", timeframe=Timeframe.M1)

    assert candles == candles_before
    assert all(c1 is c2 for c1, c2 in zip(candles, candles_before))
