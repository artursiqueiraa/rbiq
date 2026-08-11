import pytest

from app.strategies.mean_reversion import MeanReversion
from app.strategies.types import SignalDirection
from tests.strategies.conftest import (
    MEAN_REVERSION_CALL_CLOSES,
    MEAN_REVERSION_CALL_OPENS,
    MEAN_REVERSION_PUT_CLOSES,
    MEAN_REVERSION_PUT_OPENS,
    STRONG_BULLISH_TREND,
    build_context,
    make_candles,
)


def test_lower_band_rejection_fires_call():
    candles = make_candles(MEAN_REVERSION_CALL_CLOSES, opens=MEAN_REVERSION_CALL_OPENS)
    strategy = MeanReversion()
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal is not None
    assert evaluation.signal.direction == SignalDirection.CALL
    assert "price_near_lower_band" in evaluation.triggered_conditions


def test_upper_band_rejection_fires_put():
    candles = make_candles(MEAN_REVERSION_PUT_CLOSES, opens=MEAN_REVERSION_PUT_OPENS)
    strategy = MeanReversion()
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal is not None
    assert evaluation.signal.direction == SignalDirection.PUT


def test_trending_market_is_incompatible_regime():
    """Section 25: mean reversion must not fire in a real trend, even if RSI
    happens to be extreme."""
    candles = make_candles(STRONG_BULLISH_TREND)
    strategy = MeanReversion()
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal is None
    assert "regime_compatible" in evaluation.failed_conditions


def test_rejection_evidence_is_required_not_just_rsi():
    """Section 26: without an actual rejection candle (here: a doji, open ==
    close, so there's no bounce evidence), the setup must not fire even
    though price is still near the band."""
    candles = make_candles(MEAN_REVERSION_CALL_CLOSES, opens=MEAN_REVERSION_CALL_CLOSES)  # open == close: no rejection
    strategy = MeanReversion()
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal is None
    assert "rejection_evidence" in evaluation.failed_conditions


def test_insufficient_data():
    candles = make_candles([10])
    strategy = MeanReversion()
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal is None
    assert any("insufficient_data" in d for d in evaluation.diagnostics)


@pytest.mark.parametrize(
    "kwargs",
    [{"bollinger_period": 0}, {"bollinger_std": -1}, {"rsi_oversold": 80, "rsi_overbought": 70}],
)
def test_rejects_invalid_parameters(kwargs):
    with pytest.raises(ValueError):
        MeanReversion(**kwargs)
