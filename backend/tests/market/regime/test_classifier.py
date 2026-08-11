from app.market.regime.classifier import classify_regime, direction_from_structure
from app.market.types import MarketDirection, MarketRegime, StructureState, VolatilityRegime


def test_direction_mapping_is_total_and_matches_structure():
    assert direction_from_structure(StructureState.BULLISH) == MarketDirection.BULLISH
    assert direction_from_structure(StructureState.BEARISH) == MarketDirection.BEARISH
    assert direction_from_structure(StructureState.RANGE) == MarketDirection.NEUTRAL
    assert direction_from_structure(StructureState.TRANSITION) == MarketDirection.NEUTRAL
    assert direction_from_structure(StructureState.UNKNOWN) == MarketDirection.UNKNOWN


def test_bullish_structure_is_trending_bullish_regardless_of_volatility():
    assert classify_regime(StructureState.BULLISH, VolatilityRegime.HIGH) == MarketRegime.TRENDING_BULLISH
    assert classify_regime(StructureState.BULLISH, VolatilityRegime.LOW) == MarketRegime.TRENDING_BULLISH


def test_bearish_structure_is_trending_bearish():
    assert classify_regime(StructureState.BEARISH, VolatilityRegime.NORMAL) == MarketRegime.TRENDING_BEARISH


def test_transition_structure_is_transition_regime():
    assert classify_regime(StructureState.TRANSITION, VolatilityRegime.NORMAL) == MarketRegime.TRANSITION


def test_range_with_normal_volatility_is_ranging():
    assert classify_regime(StructureState.RANGE, VolatilityRegime.NORMAL) == MarketRegime.RANGING


def test_range_with_high_volatility_is_high_volatility_regime():
    assert classify_regime(StructureState.RANGE, VolatilityRegime.HIGH) == MarketRegime.HIGH_VOLATILITY


def test_range_with_low_volatility_is_low_volatility_regime():
    assert classify_regime(StructureState.RANGE, VolatilityRegime.LOW) == MarketRegime.LOW_VOLATILITY


def test_unknown_structure_is_unknown_regime():
    assert classify_regime(StructureState.UNKNOWN, VolatilityRegime.HIGH) == MarketRegime.UNKNOWN
