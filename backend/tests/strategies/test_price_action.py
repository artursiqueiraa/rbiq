import dataclasses

import pytest

from app.strategies.price_action import PriceAction
from app.strategies.types import SignalDirection
from tests.strategies.conftest import (
    PRICE_ACTION_RESISTANCE_REJECTION_CLOSES,
    PRICE_ACTION_RESISTANCE_REJECTION_HIGHS,
    PRICE_ACTION_RESISTANCE_REJECTION_LOWS,
    PRICE_ACTION_RESISTANCE_REJECTION_OPENS,
    PRICE_ACTION_SUPPORT_REJECTION_CLOSES,
    PRICE_ACTION_SUPPORT_REJECTION_HIGHS,
    PRICE_ACTION_SUPPORT_REJECTION_LOWS,
    PRICE_ACTION_SUPPORT_REJECTION_OPENS,
    RANGE_WAVE,
    STRONG_BEARISH_TREND,
    STRONG_BULLISH_TREND,
    build_context,
    make_candles,
)


def test_support_rejection_fires_call():
    candles = make_candles(
        PRICE_ACTION_SUPPORT_REJECTION_CLOSES,
        highs=PRICE_ACTION_SUPPORT_REJECTION_HIGHS,
        lows=PRICE_ACTION_SUPPORT_REJECTION_LOWS,
        opens=PRICE_ACTION_SUPPORT_REJECTION_OPENS,
    )
    strategy = PriceAction()
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal is not None
    assert evaluation.signal.direction == SignalDirection.CALL


def test_resistance_rejection_fires_put():
    candles = make_candles(
        PRICE_ACTION_RESISTANCE_REJECTION_CLOSES,
        highs=PRICE_ACTION_RESISTANCE_REJECTION_HIGHS,
        lows=PRICE_ACTION_RESISTANCE_REJECTION_LOWS,
        opens=PRICE_ACTION_RESISTANCE_REJECTION_OPENS,
    )
    strategy = PriceAction()
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal is not None
    assert evaluation.signal.direction == SignalDirection.PUT


def test_structural_continuation_fires_call_in_a_bullish_trend():
    candles = make_candles(STRONG_BULLISH_TREND)
    strategy = PriceAction()
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal is not None
    assert evaluation.signal.direction == SignalDirection.CALL


def test_structural_continuation_fires_put_in_a_bearish_trend():
    candles = make_candles(STRONG_BEARISH_TREND)
    strategy = PriceAction()
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal is not None
    assert evaluation.signal.direction == SignalDirection.PUT


def test_ambiguous_range_without_rejection_or_continuation_gives_no_signal():
    candles = make_candles(RANGE_WAVE)
    strategy = PriceAction()
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal is None


def test_wick_ratio_definition_is_mathematical_not_vague():
    """Section 29: a candle with a small wick relative to its range must not
    qualify as a rejection candle, regardless of touching a zone."""
    closes = RANGE_WAVE + [10.0]
    opens = RANGE_WAVE + [9.9]
    highs = [c + 0.5 for c in RANGE_WAVE] + [10.1]
    lows = [c - 0.5 for c in RANGE_WAVE] + [9.85]  # tiny lower wick, not a rejection shape
    candles = make_candles(closes, highs=highs, lows=lows, opens=opens)
    strategy = PriceAction(min_wick_ratio=0.5)
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal is None


def test_insufficient_data():
    strategy = PriceAction()
    ctx = build_context(make_candles([10]), strategy)
    ctx = dataclasses.replace(ctx, candles=[])
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal is None
    assert any("insufficient_data" in d for d in evaluation.diagnostics)


@pytest.mark.parametrize("kwargs", [{"min_wick_ratio": 1.5}, {"max_body_ratio": -0.1}])
def test_rejects_invalid_parameters(kwargs):
    with pytest.raises(ValueError):
        PriceAction(**kwargs)
