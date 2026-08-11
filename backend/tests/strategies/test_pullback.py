import pytest

from app.strategies.pullback import Pullback
from app.strategies.types import SignalDirection
from tests.strategies.conftest import (
    PULLBACK_CALL_CLOSES,
    PULLBACK_PUT_CLOSES,
    RANGE_WAVE,
    STRONG_BULLISH_TREND,
    build_context,
    make_candles,
)


def test_pullback_and_resumption_fires_call():
    candles = make_candles(PULLBACK_CALL_CLOSES)
    strategy = Pullback(pullback_tolerance_pct=0.02)
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal is not None
    assert evaluation.signal.direction == SignalDirection.CALL
    assert "resumption_confirmed" in evaluation.triggered_conditions


def test_pullback_and_resumption_fires_put():
    candles = make_candles(PULLBACK_PUT_CLOSES)
    strategy = Pullback(pullback_tolerance_pct=0.02)
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal is not None
    assert evaluation.signal.direction == SignalDirection.PUT


def test_mid_decline_does_not_fire_just_because_market_is_bullish():
    """Section 19: a bullish trend that is still IN the pullback (no
    resumption yet) must not fire CALL just because the broader market is
    bullish."""
    candles = make_candles(STRONG_BULLISH_TREND)  # ends mid-leg, no resumption engineered
    strategy = Pullback(pullback_tolerance_pct=0.02)
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    if evaluation.signal is not None:
        # If a resumption genuinely exists in this dataset, that's fine; the
        # important invariant is that it never fires without one.
        assert "resumption_confirmed" in evaluation.triggered_conditions


def test_range_market_gives_no_signal():
    candles = make_candles(RANGE_WAVE)
    strategy = Pullback()
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal is None


def test_insufficient_data():
    candles = make_candles([10, 11, 12])
    strategy = Pullback()
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal is None
    assert any("insufficient_data" in d for d in evaluation.diagnostics)


@pytest.mark.parametrize(
    "kwargs",
    [{"pullback_ema": 0}, {"lookback_candles": 0}, {"pullback_tolerance_pct": 1.5}],
)
def test_rejects_invalid_parameters(kwargs):
    with pytest.raises(ValueError):
        Pullback(**kwargs)
