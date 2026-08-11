import pytest

from app.indicators.atr import ATR, atr_series, true_range_series
from tests.indicators.conftest import assert_series_close, make_candles


def test_true_range_reference_values():
    highs = [10, 11, 12, 9, 10]
    lows = [8, 9, 10, 7, 8]
    closes = [9, 10, 11, 8, 9]
    # TR[0] = high-low (no previous close). TR[3] is the wide one: prev close
    # was 11, so |9-11| and |7-11|=4 dominate high-low=2.
    assert true_range_series(highs, lows, closes) == [2, 2, 2, 4, 2]


def test_atr_reference_values():
    highs = [10, 11, 12, 9, 10]
    lows = [8, 9, 10, 7, 8]
    closes = [9, 10, 11, 8, 9]
    assert_series_close(atr_series(highs, lows, closes, period=3), [None, None, 2.0, 2.6666666666666665, 2.444444444444444])


def test_constant_range_gives_constant_atr():
    highs = [10.0] * 6
    lows = [8.0] * 6
    closes = [9.0] * 6
    result = atr_series(highs, lows, closes, period=3)
    assert result[2] == pytest.approx(2.0)
    assert result[5] == pytest.approx(2.0)


def test_empty_input():
    assert true_range_series([], [], []) == []
    assert atr_series([], [], [], 14) == []


def test_insufficient_data_returns_all_none():
    assert atr_series([10.0, 11.0], [9.0, 10.0], [9.5, 10.5], 14) == [None, None]


def test_rejects_non_positive_period():
    with pytest.raises(ValueError):
        ATR(period=0)


def test_indicator_class_shape():
    candles = make_candles(
        closes=[9, 10, 11, 8, 9],
        highs=[10, 11, 12, 9, 10],
        lows=[8, 9, 10, 7, 8],
    )
    result = ATR(period=3).calculate(candles)
    assert result.name == "ATR"
    assert result.parameters == {"period": 3}
    assert_series_close(result.series["value"], [None, None, 2.0, 2.6666666666666665, 2.444444444444444])
