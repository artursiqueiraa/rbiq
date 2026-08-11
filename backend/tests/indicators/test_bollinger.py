import pytest

from app.indicators.bollinger import Bollinger, bollinger_series
from tests.indicators.conftest import assert_series_close, make_candles


def test_reference_values():
    # Hand-verified: population stdev of each 3-window of [10,12,14,12,10].
    closes = [10, 12, 14, 12, 10]
    middle, upper, lower = bollinger_series(closes, period=3, std_multiplier=2)
    assert_series_close(middle, [None, None, 12.0, 12.666666666666666, 12.0])
    assert_series_close(upper, [None, None, 15.265986323710905, 14.552284749830793, 15.265986323710905])
    assert_series_close(lower, [None, None, 8.734013676289095, 10.781048583502539, 8.734013676289095])


def test_constant_series_has_zero_width():
    middle, upper, lower = bollinger_series([50.0] * 5, period=3, std_multiplier=2)
    assert_series_close(middle, [None, None, 50.0, 50.0, 50.0])
    assert_series_close(upper, [None, None, 50.0, 50.0, 50.0])
    assert_series_close(lower, [None, None, 50.0, 50.0, 50.0])


def test_upper_always_above_middle_above_lower():
    closes = [10, 12, 9, 15, 11, 8, 14, 13]
    middle, upper, lower = bollinger_series(closes, period=3, std_multiplier=2)
    for m, u, l in zip(middle, upper, lower):
        if m is not None:
            assert u >= m >= l


def test_empty_input():
    middle, upper, lower = bollinger_series([], 20, 2)
    assert middle == upper == lower == []


def test_insufficient_data_returns_all_none():
    middle, upper, lower = bollinger_series([1.0, 2.0], 20, 2)
    assert middle == [None, None]


def test_rejects_invalid_parameters():
    with pytest.raises(ValueError):
        Bollinger(period=0)
    with pytest.raises(ValueError):
        Bollinger(std_multiplier=0)
    with pytest.raises(ValueError):
        Bollinger(std_multiplier=-1)


def test_indicator_class_shape():
    candles = make_candles([10, 12, 14, 12, 10])
    result = Bollinger(period=3, std_multiplier=2).calculate(candles)
    assert result.name == "BOLLINGER"
    assert result.parameters == {"period": 3, "std_multiplier": 2}
    assert set(result.series.keys()) == {"middle", "upper", "lower"}
