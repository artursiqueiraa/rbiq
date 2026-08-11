import pytest

from app.indicators.cci import CCI, cci_series
from tests.indicators.conftest import assert_series_close, make_candles

HIGHS = [10, 12, 13, 11, 14]
LOWS = [8, 9, 10, 9, 11]
CLOSES = [9, 11, 12, 10, 13]


def test_reference_values():
    assert_series_close(
        cci_series(HIGHS, LOWS, CLOSES, period=3),
        [None, None, 84.61538461538467, -87.49999999999994, 84.61538461538467],
    )


def test_constant_series_is_zero_not_a_crash():
    highs = [10.0] * 5
    lows = [10.0] * 5
    closes = [10.0] * 5
    result = cci_series(highs, lows, closes, period=3)
    assert result[2] == pytest.approx(0.0)


def test_extreme_values_do_not_crash():
    highs = [1_000_000.0, 999_999.0, 1_000_001.0, 1_000_500.0]
    lows = [999_998.0, 999_997.0, 999_999.0, 1_000_000.0]
    closes = [999_999.0, 999_998.0, 1_000_000.0, 1_000_200.0]
    result = cci_series(highs, lows, closes, period=3)
    assert len(result) == 4


def test_empty_input():
    assert cci_series([], [], [], 20) == []


def test_insufficient_data_returns_all_none():
    assert cci_series([10.0, 11.0], [9.0, 10.0], [9.5, 10.5], 20) == [None, None]


def test_rejects_non_positive_period():
    with pytest.raises(ValueError):
        CCI(period=0)


def test_indicator_class_shape():
    candles = make_candles(closes=CLOSES, highs=HIGHS, lows=LOWS)
    result = CCI(period=3).calculate(candles)
    assert result.name == "CCI"
    assert result.parameters == {"period": 3}
    assert_series_close(result.series["value"], [None, None, 84.61538461538467, -87.49999999999994, 84.61538461538467])
