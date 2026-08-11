import pytest

from app.indicators.macd import MACD, macd_series
from tests.indicators.conftest import assert_series_close, make_candles


def test_reference_values_macd_line():
    # Hand-verified spot check: flat prices produce EMA==price, so macd_line is
    # 0 until the jump at the last point makes the fast EMA (period 2) pull
    # ahead of the slow EMA (period 3).
    closes = [10, 10, 10, 10, 20]
    macd_line, signal, histogram = macd_series(closes, fast_period=2, slow_period=3, signal_period=2)
    assert_series_close(macd_line, [None, None, 0.0, 0.0, 1.6666666666666643])
    assert_series_close(signal, [None, None, None, 0.0, 1.1111111111111094])
    assert_series_close(histogram, [None, None, None, 0.0, 0.5555555555555549])


def test_histogram_is_macd_minus_signal_everywhere_defined():
    closes = [22, 24, 23, 25, 27, 26, 29, 30, 28, 31]
    macd_line, signal, histogram = macd_series(closes, fast_period=3, slow_period=5, signal_period=2)
    for m, s, h in zip(macd_line, signal, histogram):
        if m is None or s is None:
            assert h is None
        else:
            assert h == pytest.approx(m - s)


def test_macd_line_equals_fast_minus_slow_ema_everywhere_defined():
    from app.indicators.ema import ema_series

    closes = [5, 6, 5, 7, 8, 6, 9, 10, 8, 11]
    fast, slow, signal_period = 3, 5, 2
    macd_line, _, _ = macd_series(closes, fast, slow, signal_period)
    ema_fast = ema_series(closes, fast)
    ema_slow = ema_series(closes, slow)
    for m, f, s in zip(macd_line, ema_fast, ema_slow):
        if f is None or s is None:
            assert m is None
        else:
            assert m == pytest.approx(f - s)


def test_empty_input():
    macd_line, signal, histogram = macd_series([], 12, 26, 9)
    assert macd_line == signal == histogram == []


def test_insufficient_data_returns_all_none():
    macd_line, signal, histogram = macd_series([1.0, 2.0], 12, 26, 9)
    assert macd_line == [None, None]
    assert signal == [None, None]
    assert histogram == [None, None]


def test_rejects_non_positive_periods():
    with pytest.raises(ValueError):
        MACD(fast_period=0)
    with pytest.raises(ValueError):
        MACD(slow_period=-1)
    with pytest.raises(ValueError):
        MACD(signal_period=0)


def test_indicator_class_shape():
    candles = make_candles([10, 10, 10, 10, 20])
    result = MACD(fast_period=2, slow_period=3, signal_period=2).calculate(candles)
    assert result.name == "MACD"
    assert result.parameters == {"fast_period": 2, "slow_period": 3, "signal_period": 2}
    assert set(result.series.keys()) == {"macd", "signal", "histogram"}
