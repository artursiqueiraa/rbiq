import pytest

from app.indicators.stochastic import Stochastic, stochastic_series
from tests.indicators.conftest import assert_series_close, make_candles

HIGHS = [10, 12, 13, 11, 14]
LOWS = [8, 9, 10, 9, 11]
CLOSES = [9, 11, 12, 10, 13]


def test_reference_values_raw_k_smooth_1():
    # Hand-verified: with smooth=1, %K is the raw stochastic (no extra smoothing).
    k, d = stochastic_series(HIGHS, LOWS, CLOSES, k_period=3, d_period=2, smooth=1)
    assert_series_close(k, [None, None, 80.0, 25.0, 80.0])
    assert_series_close(d, [None, None, None, 52.5, 52.5])


def test_values_stay_within_0_100():
    k, d = stochastic_series(HIGHS, LOWS, CLOSES, k_period=3, d_period=3, smooth=3)
    for series in (k, d):
        for value in series:
            if value is not None:
                assert 0.0 <= value <= 100.0


def test_flat_window_is_neutral_fifty_not_a_crash():
    highs = [10.0] * 5
    lows = [10.0] * 5
    closes = [10.0] * 5
    k, _ = stochastic_series(highs, lows, closes, k_period=3, d_period=2, smooth=1)
    assert k[2] == pytest.approx(50.0)


def test_empty_input():
    k, d = stochastic_series([], [], [], 14, 3, 3)
    assert k == d == []


def test_insufficient_data_returns_all_none():
    k, d = stochastic_series([10.0, 11.0], [9.0, 10.0], [9.5, 10.5], 14, 3, 3)
    assert k == [None, None]


def test_rejects_non_positive_parameters():
    with pytest.raises(ValueError):
        Stochastic(k_period=0)
    with pytest.raises(ValueError):
        Stochastic(d_period=0)
    with pytest.raises(ValueError):
        Stochastic(smooth=0)


def test_indicator_class_shape():
    candles = make_candles(closes=CLOSES, highs=HIGHS, lows=LOWS)
    result = Stochastic(k_period=3, d_period=2, smooth=1).calculate(candles)
    assert result.name == "STOCHASTIC"
    assert result.parameters == {"k_period": 3, "d_period": 2, "smooth": 1}
    assert set(result.series.keys()) == {"k", "d"}
