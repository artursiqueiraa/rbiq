import pytest

from app.indicators import ATR, CCI, EMA, MACD, RSI, SMA, Bollinger, IndicatorRegistry, Stochastic, calculate_indicators
from tests.indicators.conftest import make_candles


@pytest.mark.parametrize("name,cls", [
    ("SMA", SMA), ("EMA", EMA), ("RSI", RSI), ("MACD", MACD),
    ("BOLLINGER", Bollinger), ("ATR", ATR), ("STOCHASTIC", Stochastic), ("CCI", CCI),
])
def test_get_returns_the_right_class(name, cls):
    assert IndicatorRegistry.get(name) is cls


def test_get_is_case_insensitive():
    assert IndicatorRegistry.get("sma") is SMA
    assert IndicatorRegistry.get("Sma") is SMA


def test_unknown_indicator_raises_value_error():
    with pytest.raises(ValueError):
        IndicatorRegistry.get("NOT_A_REAL_INDICATOR")


def test_create_builds_a_configured_instance():
    indicator = IndicatorRegistry.create("EMA", period=20)
    assert isinstance(indicator, EMA)
    assert indicator.period == 20


def test_names_lists_all_eight():
    assert IndicatorRegistry.names() == ["ATR", "BOLLINGER", "CCI", "EMA", "MACD", "RSI", "SMA", "STOCHASTIC"]


def test_calculate_indicators_keys_by_name_and_parameters():
    candles = make_candles([10, 11, 12, 13, 14, 15, 16, 17, 18, 19])
    results = calculate_indicators(candles, [SMA(period=3), EMA(period=3), RSI(period=3)])
    assert set(results.keys()) == {"SMA_3", "EMA_3", "RSI_3"}


def test_calculate_indicators_distinguishes_different_parameterizations():
    candles = make_candles([10, 11, 12, 13, 14, 15, 16, 17, 18, 19])
    results = calculate_indicators(candles, [EMA(period=3), EMA(period=5)])
    assert set(results.keys()) == {"EMA_3", "EMA_5"}
    assert results["EMA_3"].series["value"] != results["EMA_5"].series["value"]
