import pytest

from app.indicators.ema import EMA, ema_series
from tests.indicators.conftest import assert_series_close, make_candles


def test_reference_values():
    # Hand-verified: EMA(3), alpha=0.5, seeded with SMA(3) at index 2.
    values = [22, 24, 23, 25, 27, 26, 29]
    assert_series_close(ema_series(values, 3), [None, None, 23.0, 24.0, 25.5, 25.75, 27.375])


def test_seed_equals_sma_at_seed_index():
    values = [5, 7, 6, 9, 8]
    result = ema_series(values, 3)
    assert result[2] == pytest.approx((5 + 7 + 6) / 3)


def test_constant_series_stays_constant():
    assert_series_close(ema_series([50.0] * 6, 3), [None, None, 50.0, 50.0, 50.0, 50.0])


def test_empty_input():
    assert ema_series([], 3) == []


def test_insufficient_data_returns_all_none():
    assert ema_series([1.0, 2.0], 5) == [None, None]


def test_rejects_non_positive_period():
    with pytest.raises(ValueError):
        EMA(period=0)


def test_indicator_class_shape():
    candles = make_candles([22, 24, 23, 25, 27, 26, 29])
    result = EMA(period=3).calculate(candles)
    assert result.name == "EMA"
    assert result.parameters == {"period": 3}
    assert_series_close(result.series["value"], [None, None, 23.0, 24.0, 25.5, 25.75, 27.375])
