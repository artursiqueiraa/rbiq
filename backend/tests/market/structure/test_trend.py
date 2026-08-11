from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.market.structure.trend import SwingComparison, classify_state, compare_swing
from app.market.types import StructureState, SwingPoint, SwingType

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def swing(price, type_=SwingType.HIGH, index=0):
    return SwingPoint(
        type=type_,
        timestamp=BASE + timedelta(minutes=index),
        confirmation_timestamp=BASE + timedelta(minutes=index + 2),
        price=Decimal(str(price)),
        index=index,
        strength=1.0,
    )


def test_compare_swing_higher():
    assert compare_swing(swing(15, index=1), swing(10, index=0)) == SwingComparison.HIGHER


def test_compare_swing_lower():
    assert compare_swing(swing(5, index=1), swing(10, index=0)) == SwingComparison.LOWER


def test_compare_swing_equal():
    assert compare_swing(swing(10, index=1), swing(10, index=0)) == SwingComparison.EQUAL


def test_classify_state_unknown_with_fewer_than_two_of_either_type():
    assert classify_state([swing(10)], [swing(5), swing(6)]) == StructureState.UNKNOWN
    assert classify_state([swing(10), swing(12)], [swing(5)]) == StructureState.UNKNOWN
    assert classify_state([], []) == StructureState.UNKNOWN


def test_hh_plus_hl_is_bullish():
    highs = [swing(10, SwingType.HIGH, 0), swing(15, SwingType.HIGH, 2)]
    lows = [swing(5, SwingType.LOW, 1), swing(8, SwingType.LOW, 3)]
    assert classify_state(highs, lows) == StructureState.BULLISH


def test_ll_plus_lh_is_bearish():
    highs = [swing(15, SwingType.HIGH, 0), swing(10, SwingType.HIGH, 2)]
    lows = [swing(8, SwingType.LOW, 1), swing(5, SwingType.LOW, 3)]
    assert classify_state(highs, lows) == StructureState.BEARISH


def test_mixed_hh_plus_ll_is_transition():
    highs = [swing(10, SwingType.HIGH, 0), swing(15, SwingType.HIGH, 2)]  # HH
    lows = [swing(8, SwingType.LOW, 1), swing(5, SwingType.LOW, 3)]  # LL
    assert classify_state(highs, lows) == StructureState.TRANSITION


def test_mixed_lh_plus_hl_is_transition():
    highs = [swing(15, SwingType.HIGH, 0), swing(10, SwingType.HIGH, 2)]  # LH
    lows = [swing(5, SwingType.LOW, 1), swing(8, SwingType.LOW, 3)]  # HL
    assert classify_state(highs, lows) == StructureState.TRANSITION


def test_equal_high_is_range():
    highs = [swing(10, SwingType.HIGH, 0), swing(10, SwingType.HIGH, 2)]
    lows = [swing(5, SwingType.LOW, 1), swing(8, SwingType.LOW, 3)]
    assert classify_state(highs, lows) == StructureState.RANGE


def test_equal_low_is_range():
    highs = [swing(10, SwingType.HIGH, 0), swing(15, SwingType.HIGH, 2)]
    lows = [swing(5, SwingType.LOW, 1), swing(5, SwingType.LOW, 3)]
    assert classify_state(highs, lows) == StructureState.RANGE


def test_only_the_two_most_recent_swings_matter():
    highs = [swing(20, SwingType.HIGH, 0), swing(10, SwingType.HIGH, 2), swing(15, SwingType.HIGH, 4)]
    lows = [swing(1, SwingType.LOW, 1), swing(5, SwingType.LOW, 3), swing(8, SwingType.LOW, 5)]
    # ignoring the oldest high (20), the last two are 10 -> 15 = HIGHER; lows 5 -> 8 = HIGHER
    assert classify_state(highs, lows) == StructureState.BULLISH
