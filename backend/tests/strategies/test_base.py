from app.strategies.base import ConditionCheck, classify_strength, decide_direction, last_value, value_at
from app.strategies.types import SignalDirection, SignalStrength


def test_classify_strength_thresholds():
    assert classify_strength(0.85) == SignalStrength.STRONG
    assert classify_strength(1.0) == SignalStrength.STRONG
    assert classify_strength(0.65) == SignalStrength.MEDIUM
    assert classify_strength(0.84) == SignalStrength.MEDIUM
    assert classify_strength(0.64) == SignalStrength.WEAK
    assert classify_strength(0.0) == SignalStrength.WEAK


def test_decide_direction_bullish_wins():
    bullish = [ConditionCheck("a", True), ConditionCheck("b", True), ConditionCheck("c", False)]
    bearish = [ConditionCheck("a", False), ConditionCheck("b", False)]
    direction, confidence, triggered, failed = decide_direction(bullish, bearish, min_confidence=0.5)
    assert direction == SignalDirection.CALL
    assert confidence == 2 / 3
    assert triggered == ["a", "b"]
    assert failed == ["c"]


def test_decide_direction_bearish_wins():
    bullish = [ConditionCheck("a", False)]
    bearish = [ConditionCheck("a", True), ConditionCheck("b", True)]
    direction, confidence, *_ = decide_direction(bullish, bearish, min_confidence=0.5)
    assert direction == SignalDirection.PUT
    assert confidence == 1.0


def test_decide_direction_below_threshold_is_none():
    bullish = [ConditionCheck("a", True), ConditionCheck("b", False)]
    bearish = [ConditionCheck("a", False), ConditionCheck("b", False)]
    direction, confidence, *_ = decide_direction(bullish, bearish, min_confidence=0.75)
    assert direction == SignalDirection.NONE
    assert confidence == 0.5  # still reported for diagnostics


def test_decide_direction_tie_is_none():
    bullish = [ConditionCheck("a", True), ConditionCheck("b", False)]
    bearish = [ConditionCheck("a", True), ConditionCheck("b", False)]
    direction, confidence, *_ = decide_direction(bullish, bearish, min_confidence=0.5)
    assert direction == SignalDirection.NONE


def test_decide_direction_empty_checks_is_none():
    direction, confidence, triggered, failed = decide_direction([], [], min_confidence=0.5)
    assert direction == SignalDirection.NONE
    assert confidence == 0.0
    assert triggered == []
    assert failed == []


def test_last_value_returns_most_recent_non_none():
    assert last_value([1.0, 2.0, None]) == 2.0
    assert last_value([None, None]) is None
    assert last_value([]) is None


def test_value_at_returns_none_out_of_range():
    assert value_at([1.0, 2.0], 5) is None
    assert value_at([1.0, 2.0], -1) is None
    assert value_at([1.0, 2.0], 1) == 2.0
