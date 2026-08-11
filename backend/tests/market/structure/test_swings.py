import pytest

from app.market.structure.swings import detect_swings
from app.market.types import SwingType
from tests.market.conftest import BULLISH_CLOSES, make_candles


def test_simple_swing_high_is_confirmed_with_correct_timestamps():
    # rise to a peak at index 5, then decline -> confirmed once index 7 exists (right_bars=2)
    closes = [10, 11, 12, 13, 14, 15, 14, 13]
    candles = make_candles(closes)
    swings = detect_swings(candles, left_bars=2, right_bars=2)

    highs = [s for s in swings if s.type == SwingType.HIGH]
    assert len(highs) == 1
    assert highs[0].index == 5
    assert highs[0].price == candles[5].high
    assert highs[0].timestamp == candles[5].timestamp
    assert highs[0].confirmation_timestamp == candles[7].timestamp
    assert highs[0].confirmation_timestamp > highs[0].timestamp


def test_simple_swing_low_is_confirmed_with_correct_timestamps():
    closes = [15, 14, 13, 12, 11, 10, 11, 12]
    candles = make_candles(closes)
    swings = detect_swings(candles, left_bars=2, right_bars=2)

    lows = [s for s in swings if s.type == SwingType.LOW]
    assert len(lows) == 1
    assert lows[0].index == 5
    assert lows[0].confirmation_timestamp == candles[7].timestamp


def test_multiple_swings_in_bullish_dataset():
    candles = make_candles(BULLISH_CLOSES)
    swings = detect_swings(candles, left_bars=2, right_bars=2)
    assert len(swings) == 4
    assert [s.index for s in swings] == [5, 8, 13, 16]
    assert [s.type for s in swings] == [SwingType.HIGH, SwingType.LOW, SwingType.HIGH, SwingType.LOW]


def test_tied_high_only_flags_the_leftmost_occurrence():
    # two candles share the exact same high within one window
    closes = [10, 11, 15, 12, 15, 11, 10]
    highs = [10.5, 11.5, 15.0, 12.5, 15.0, 11.5, 10.5]
    candles = make_candles(closes, highs=highs)
    swings = detect_swings(candles, left_bars=2, right_bars=2)
    highs_found = [s for s in swings if s.type == SwingType.HIGH]
    assert len(highs_found) == 1
    assert highs_found[0].index == 2  # the leftmost of the tie


def test_insufficient_data_returns_no_swings():
    candles = make_candles([10, 11, 12])  # fewer than left_bars+right_bars+1
    assert detect_swings(candles, left_bars=2, right_bars=2) == []


def test_empty_input():
    assert detect_swings([], left_bars=2, right_bars=2) == []


def test_delayed_confirmation_only_returns_swings_with_enough_trailing_candles():
    # A peak at index 5 needs right_bars=2 trailing candles (indices 6,7) to confirm.
    # With only 6 candles (indices 0-5), it isn't confirmable yet.
    closes = [10, 11, 12, 13, 14, 15]
    candles = make_candles(closes)
    assert detect_swings(candles, left_bars=2, right_bars=2) == []

    # Adding the 2 trailing candles makes it confirmable.
    candles_extended = make_candles(closes + [14, 13])
    swings = detect_swings(candles_extended, left_bars=2, right_bars=2)
    assert len(swings) == 1
    assert swings[0].index == 5


def test_rejects_negative_bar_counts():
    candles = make_candles([10, 11, 12, 13, 14])
    with pytest.raises(ValueError):
        detect_swings(candles, left_bars=-1, right_bars=2)
    with pytest.raises(ValueError):
        detect_swings(candles, left_bars=2, right_bars=-1)


def test_strength_is_non_negative():
    candles = make_candles(BULLISH_CLOSES)
    swings = detect_swings(candles, left_bars=2, right_bars=2)
    assert all(s.strength >= 0 for s in swings)
