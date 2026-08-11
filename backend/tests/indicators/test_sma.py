import pytest

from app.indicators.sma import SMA, sma_series
from tests.indicators.conftest import assert_series_close, make_candles


def test_reference_values():
    # Hand-verified: SMA(3) of [10,11,12,13,14] -> mean of each 3-window.
    assert_series_close(sma_series([10, 11, 12, 13, 14], 3), [None, None, 11.0, 12.0, 13.0])


def test_constant_series():
    assert_series_close(sma_series([100.0] * 5, 3), [None, None, 100.0, 100.0, 100.0])


def test_increasing_series():
    assert_series_close(sma_series([100, 101, 102, 103, 104], 2), [None, 100.5, 101.5, 102.5, 103.5])


def test_decreasing_series():
    assert_series_close(sma_series([104, 103, 102, 101, 100], 2), [None, 103.5, 102.5, 101.5, 100.5])


def test_empty_input():
    assert sma_series([], 3) == []


def test_insufficient_data_returns_all_none():
    assert sma_series([1.0, 2.0], 5) == [None, None]


def test_rejects_non_positive_period():
    with pytest.raises(ValueError):
        SMA(period=0)
    with pytest.raises(ValueError):
        SMA(period=-1)


def test_indicator_class_shape():
    result = SMA(period=3).calculate(make_candles([10, 11, 12, 13, 14]))
    assert result.name == "SMA"
    assert result.parameters == {"period": 3}
    assert_series_close(result.series["value"], [None, None, 11.0, 12.0, 13.0])
