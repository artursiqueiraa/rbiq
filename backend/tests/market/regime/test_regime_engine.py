import pytest

from app.market.regime.regime_engine import compute_regime, compute_trend_strength
from app.market.types import MarketDirection, MarketRegime, StructureState, VolatilityRegime


def test_trend_strength_reference_value():
    ema = [None, None, None, None, 10, 12, 14, 16, 18, 20]
    atr = [None, None, None, None, 2, 2, 2, 2, 2, 2]
    # slope = (20 - 14) / 3 = 2.0; normalized = 2.0 / atr[-1](2) = 1.0, clipped to 1.0
    assert compute_trend_strength(ema, atr, slope_period=3) == pytest.approx(1.0)


def test_trend_strength_is_scaled_by_atr():
    ema = [None, None, None, None, 10, 12, 14, 16, 18, 20]
    atr = [None, None, None, None, 8, 8, 8, 8, 8, 8]
    # slope = 2.0, normalized = 2.0 / 8 = 0.25
    assert compute_trend_strength(ema, atr, slope_period=3) == pytest.approx(0.25)


def test_trend_strength_none_when_not_enough_history():
    ema = [10, 12]
    atr = [2, 2]
    assert compute_trend_strength(ema, atr, slope_period=5) is None


def test_trend_strength_none_when_all_none():
    assert compute_trend_strength([None, None], [None, None]) is None


def test_trend_strength_zero_atr_gives_zero_not_a_crash():
    ema = [10, 12, 14]
    atr = [0, 0, 0]
    assert compute_trend_strength(ema, atr, slope_period=1) == 0.0


def test_trend_strength_rejects_non_positive_slope_period():
    with pytest.raises(ValueError):
        compute_trend_strength([1.0], [1.0], slope_period=0)


def test_compute_regime_wires_direction_regime_and_volatility_together():
    result = compute_regime(
        structure_state=StructureState.BULLISH,
        atr_values=[None, None, 2.0, 2.0, 2.0],
        ema_values=[None, None, 10.0, 12.0, 14.0],
        closes=[100.0, 100.0, 100.0, 100.0, 100.0],
        volatility_window=100,
        trend_slope_period=2,
    )
    assert result.direction == MarketDirection.BULLISH
    assert result.regime == MarketRegime.TRENDING_BULLISH
    assert result.volatility_value == pytest.approx(0.02)  # 2.0 / 100.0
