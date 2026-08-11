import pytest

from app.strategies.breakout import Breakout
from app.strategies.types import SignalDirection
from tests.strategies.conftest import (
    BREAKOUT_CALL_CLOSES,
    BREAKOUT_PUT_CLOSES,
    FALSE_BREAK_CLOSES,
    FALSE_BREAK_HIGHS,
    FALSE_BREAK_LOWS,
    STRONG_BULLISH_TREND,
    build_context,
    make_candles,
)


def test_confirmed_resistance_break_fires_call():
    candles = make_candles(BREAKOUT_CALL_CLOSES)
    strategy = Breakout(confirmation_candles=3)
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal is not None
    assert evaluation.signal.direction == SignalDirection.CALL
    assert "breakout_confirmed" in evaluation.triggered_conditions


def test_confirmed_support_break_fires_put():
    candles = make_candles(BREAKOUT_PUT_CLOSES)
    strategy = Breakout(confirmation_candles=3)
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal is not None
    assert evaluation.signal.direction == SignalDirection.PUT


def test_false_break_gives_no_signal():
    """Section 24/54: a wick through resistance that closes back below it
    must never fire — the confirmation check is on closes, not highs/lows."""
    candles = make_candles(FALSE_BREAK_CLOSES, highs=FALSE_BREAK_HIGHS, lows=FALSE_BREAK_LOWS)
    strategy = Breakout()
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal is None
    assert "breakout_confirmed" in evaluation.failed_conditions


def test_trending_market_is_not_a_breakout_regime():
    candles = make_candles(STRONG_BULLISH_TREND)
    strategy = Breakout()
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal is None
    assert "regime_compatible" in evaluation.failed_conditions


def test_stale_zone_on_the_wrong_side_does_not_inflate_confidence():
    """Regression test for the O(n^2)-adjacent scoring bug found while
    building this Sprint's reference datasets (see the Sprint 5 report,
    "Problemas encontrados"): a resistance zone sitting below a price that is
    actually breaking DOWN through support must not let the bullish side
    accumulate enough partial credit to fire."""
    candles = make_candles(BREAKOUT_PUT_CLOSES)
    strategy = Breakout(confirmation_candles=3)
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal.direction == SignalDirection.PUT  # not CALL


def test_insufficient_data():
    candles = make_candles([10])
    strategy = Breakout(confirmation_candles=3)
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal is None
    assert any("insufficient_data" in d for d in evaluation.diagnostics)


@pytest.mark.parametrize("kwargs", [{"confirmation_candles": 0}, {"atr_period": -1}])
def test_rejects_invalid_parameters(kwargs):
    with pytest.raises(ValueError):
        Breakout(**kwargs)
