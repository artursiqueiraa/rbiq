from app.market.regime.volatility import classify_volatility, normalized_atr_series
from app.market.types import VolatilityRegime


def test_normalized_atr_divides_by_close():
    result = normalized_atr_series([1.0, 2.0, None], [100.0, 100.0, 100.0])
    assert result == [0.01, 0.02, None]


def test_normalized_atr_handles_zero_close():
    result = normalized_atr_series([1.0], [0.0])
    assert result == [None]


def test_no_data_is_unknown():
    regime, value = classify_volatility([None, None])
    assert regime == VolatilityRegime.UNKNOWN
    assert value is None


def test_single_value_is_unknown_not_enough_to_rank():
    regime, value = classify_volatility([0.01])
    assert regime == VolatilityRegime.UNKNOWN
    assert value == 0.01


def test_latest_value_at_the_bottom_of_its_own_history_is_low():
    series = [0.05, 0.04, 0.03, 0.02, 0.01]  # decreasing; latest (0.01) is the smallest
    regime, value = classify_volatility(series)
    assert regime == VolatilityRegime.LOW
    assert value == 0.01


def test_latest_value_at_the_top_of_its_own_history_is_high():
    series = [0.01, 0.02, 0.03, 0.04, 0.05]  # increasing; latest (0.05) is the largest
    regime, value = classify_volatility(series)
    assert regime == VolatilityRegime.HIGH


def test_latest_value_in_the_middle_is_normal():
    series = [0.05, 0.01, 0.02, 0.04, 0.03]  # latest (0.03) sits mid-pack (rank 3/5)
    regime, value = classify_volatility(series)
    assert regime == VolatilityRegime.NORMAL


def test_window_limits_how_much_history_is_considered():
    # Ten old huge spikes, then a small increasing run. Against the FULL
    # history the latest value (0.05) is dwarfed by the old spikes -> LOW.
    # With window=5, only the recent run is considered, where 0.05 is the
    # largest -> HIGH. This is what the window parameter is for.
    series = [10.0] * 10 + [0.01, 0.02, 0.03, 0.04, 0.05]
    windowed_regime, _ = classify_volatility(series, window=5)
    unwindowed_regime, _ = classify_volatility(series, window=1000)
    assert windowed_regime == VolatilityRegime.HIGH
    assert unwindowed_regime == VolatilityRegime.LOW


def test_trailing_none_values_are_skipped_latest_is_last_real_value():
    series = [0.01, 0.02, 0.03, None, None]
    regime, value = classify_volatility(series)
    assert value == 0.03
