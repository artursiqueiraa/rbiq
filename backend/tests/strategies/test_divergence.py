import pytest

from app.strategies.divergence import Divergence
from app.strategies.types import SignalDirection
from tests.strategies.conftest import (
    RANGE_WAVE,
    STRONG_BEARISH_TREND,
    STRONG_BULLISH_TREND,
    build_context,
    make_candles,
)


def test_bullish_divergence_on_a_bearish_trend_fires_call():
    """A sustained decline whose RSI stops making new lows (momentum fading)
    while price keeps falling — a textbook bullish divergence. Verified by
    running the strategy against this exact dataset (see conftest)."""
    candles = make_candles(STRONG_BEARISH_TREND)
    strategy = Divergence()
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal is not None
    assert evaluation.signal.direction == SignalDirection.CALL
    assert "price_lower_low" in evaluation.triggered_conditions
    assert "rsi_higher_low" in evaluation.triggered_conditions


def test_bearish_divergence_on_a_bullish_trend_fires_put():
    candles = make_candles(STRONG_BULLISH_TREND)
    strategy = Divergence()
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal is not None
    assert evaluation.signal.direction == SignalDirection.PUT
    assert "price_higher_high" in evaluation.triggered_conditions
    assert "rsi_lower_high" in evaluation.triggered_conditions


def test_divergence_is_not_automatically_a_signal():
    """Section 31/32: divergence alone must not always translate into a
    signal — disabling the confirmation requirement and demanding perfect
    agreement on a dataset that lacks a confirming move should still be able
    to produce NONE. Here we simply demonstrate the gate exists and can
    suppress a would-be signal."""
    candles = make_candles(STRONG_BEARISH_TREND)
    lenient = Divergence()
    # The swing is older than 1 bar, so divergence_recent fails; demanding
    # near-total agreement (not just clearing the default 0.70) makes that
    # one failure enough to suppress the signal.
    strict = Divergence(max_bars_between_swings=1, min_confidence=0.95)
    ctx_lenient = build_context(candles, lenient)
    ctx_strict = build_context(candles, strict)
    assert lenient.evaluate(ctx_lenient).signal is not None
    strict_evaluation = strict.evaluate(ctx_strict)
    assert strict_evaluation.signal is None
    assert "divergence_recent" in strict_evaluation.failed_conditions


def test_no_divergence_in_a_pure_range_with_too_few_swings():
    candles = make_candles(RANGE_WAVE)
    strategy = Divergence()
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    # RANGE_WAVE's swings are all at equal prices (no Lower Low or Higher
    # High), so neither divergence condition can be satisfied even though
    # enough swings exist.
    assert evaluation.signal is None


def test_uses_the_same_causal_swings_as_the_market_engine():
    """Section 33: no separate swing algorithm — detect_swings is imported
    and called directly, not reimplemented."""
    import app.strategies.divergence as divergence_module
    from app.market.structure.swings import detect_swings

    assert divergence_module.detect_swings is detect_swings


def test_insufficient_data():
    strategy = Divergence()
    ctx = build_context(make_candles([10, 11, 12]), strategy)
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal is None


@pytest.mark.parametrize(
    "kwargs", [{"rsi_period": 0}, {"left_bars": -1}, {"max_bars_between_swings": 0}]
)
def test_rejects_invalid_parameters(kwargs):
    with pytest.raises(ValueError):
        Divergence(**kwargs)
