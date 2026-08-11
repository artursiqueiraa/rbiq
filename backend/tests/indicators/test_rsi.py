import pytest

from app.indicators.rsi import RSI, rsi_series
from tests.indicators.conftest import assert_series_close, make_candles


def test_reference_values():
    # Hand-verified Wilder's RSI(3): deltas 0.5,-1.0,1.5,1.0 -> avg_gain/avg_loss
    # seeded from the first 3 deltas, then one Wilder-smoothed step.
    closes = [44, 44.5, 43.5, 45, 46]
    assert_series_close(rsi_series(closes, 3), [None, None, None, 66.66666666666666, 77.77777777777777])


def test_strictly_increasing_series_approaches_100():
    closes = [10 + i for i in range(10)]
    result = rsi_series(closes, 3)
    assert result[-1] == pytest.approx(100.0)


def test_strictly_decreasing_series_approaches_0():
    closes = [20 - i for i in range(10)]
    result = rsi_series(closes, 3)
    assert result[-1] == pytest.approx(0.0)


def test_constant_series_has_no_zero_division_and_is_neutral():
    # No gains, no losses at all -> avg_loss == 0 -> our documented convention is 100.0
    result = rsi_series([10.0] * 8, 3)
    assert result[3] == pytest.approx(100.0)


def test_alternating_series_does_not_crash():
    closes = [10, 11, 10, 11, 10, 11, 10]
    result = rsi_series(closes, 3)
    assert len(result) == len(closes)


def test_empty_input():
    assert rsi_series([], 14) == []


def test_insufficient_data_returns_all_none():
    assert rsi_series([1.0, 2.0, 3.0], 14) == [None, None, None]


def test_rejects_non_positive_period():
    with pytest.raises(ValueError):
        RSI(period=0)


def test_indicator_class_shape():
    candles = make_candles([44, 44.5, 43.5, 45, 46])
    result = RSI(period=3).calculate(candles)
    assert result.name == "RSI"
    assert result.parameters == {"period": 3}
    assert_series_close(result.series["value"], [None, None, None, 66.66666666666666, 77.77777777777777])
