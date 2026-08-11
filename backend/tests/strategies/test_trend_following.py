import dataclasses

import pytest

from app.strategies.trend_following import TrendFollowing
from app.strategies.types import SignalDirection
from tests.strategies.conftest import (
    RANGE_WAVE,
    STRONG_BEARISH_TREND,
    STRONG_BULLISH_TREND,
    build_context,
    make_candles,
)


def test_bullish_trend_fires_call():
    candles = make_candles(STRONG_BULLISH_TREND)
    strategy = TrendFollowing()
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal is not None
    assert evaluation.signal.direction == SignalDirection.CALL
    assert evaluation.signal.strategy == "trend_following"
    assert "market_direction_bullish" in evaluation.triggered_conditions


def test_bearish_trend_fires_put():
    candles = make_candles(STRONG_BEARISH_TREND)
    strategy = TrendFollowing()
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal is not None
    assert evaluation.signal.direction == SignalDirection.PUT


def test_range_gives_no_signal():
    candles = make_candles(RANGE_WAVE)
    # Small EMA periods so the check actually runs despite RANGE_WAVE's 26
    # candles (the default slow_ema=50 would fail on "insufficient data"
    # first, which is a valid but different reason for NONE than a
    # regime mismatch — this isolates the regime check specifically).
    strategy = TrendFollowing(fast_ema=3, slow_ema=5)
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal is None
    assert "regime_compatible" in evaluation.failed_conditions


def test_weak_trend_strength_blocks_the_signal():
    candles = make_candles(STRONG_BULLISH_TREND)
    # Same market, but requiring a trend strength no real trend reaches, AND
    # near-total agreement overall (otherwise 4/5 other conditions passing
    # would still clear the default 0.70 threshold on their own).
    strategy = TrendFollowing(min_trend_strength=0.99, min_confidence=0.95)
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal is None
    assert "trend_strength_sufficient" in evaluation.failed_conditions


def test_insufficient_data_returns_no_signal_with_diagnostic():
    candles = make_candles([10, 11, 12])
    strategy = TrendFollowing()
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal is None
    assert any("insufficient_data" in d for d in evaluation.diagnostics)


def test_no_candles_at_all():
    strategy = TrendFollowing()
    ctx = build_context(make_candles([10]), strategy)
    ctx = dataclasses.replace(ctx, candles=[])
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"fast_ema": 0},
        {"fast_ema": 50, "slow_ema": 20},
        {"min_trend_strength": 1.5},
        {"min_confidence": 2.0},
        {"expiry_candles": 0},
    ],
)
def test_rejects_invalid_parameters(kwargs):
    with pytest.raises(ValueError):
        TrendFollowing(**kwargs)


def test_signal_is_explainable():
    candles = make_candles(STRONG_BULLISH_TREND)
    strategy = TrendFollowing()
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    assert len(evaluation.signal.conditions) > 0
    assert all(isinstance(c, str) and c for c in evaluation.signal.conditions)
    assert evaluation.signal.metadata["parameters"]["fast_ema"] == 20
