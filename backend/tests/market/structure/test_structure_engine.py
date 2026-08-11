from app.market.structure.structure_engine import analyze_structure
from app.market.structure.swings import detect_swings
from app.market.types import StructureEventType, StructureState
from tests.market.conftest import BEARISH_CLOSES, BREAK_CLOSES, BULLISH_CLOSES, RANGE_CLOSES, make_candles


def _analyze(closes):
    candles = make_candles(closes)
    swings = detect_swings(candles, left_bars=2, right_bars=2)
    return analyze_structure(candles, swings)


def test_hh_hl_dataset_ends_bullish():
    analysis = _analyze(BULLISH_CLOSES)
    assert analysis.state == StructureState.BULLISH
    event_types = [e.event_type for e in analysis.events]
    assert StructureEventType.HIGHER_HIGH in event_types
    assert StructureEventType.HIGHER_LOW in event_types


def test_ll_lh_dataset_ends_bearish():
    analysis = _analyze(BEARISH_CLOSES)
    assert analysis.state == StructureState.BEARISH
    event_types = [e.event_type for e in analysis.events]
    assert StructureEventType.LOWER_LOW in event_types
    assert StructureEventType.LOWER_HIGH in event_types


def test_repeating_wave_ends_in_range():
    analysis = _analyze(RANGE_CLOSES)
    assert analysis.state == StructureState.RANGE


def test_break_of_structure_is_detected_and_moves_to_transition():
    analysis = _analyze(BREAK_CLOSES)
    assert analysis.state == StructureState.TRANSITION
    breaks = [e for e in analysis.events if e.event_type == StructureEventType.STRUCTURE_BREAK]
    assert len(breaks) == 1


def test_events_are_in_chronological_order():
    analysis = _analyze(BREAK_CLOSES)
    timestamps = [e.confirmation_timestamp for e in analysis.events]
    assert timestamps == sorted(timestamps)


def test_confirmed_highs_and_lows_are_sorted_by_occurrence():
    analysis = _analyze(BULLISH_CLOSES)
    high_indices = [s.index for s in analysis.confirmed_highs]
    low_indices = [s.index for s in analysis.confirmed_lows]
    assert high_indices == sorted(high_indices)
    assert low_indices == sorted(low_indices)


def test_empty_candles_give_unknown_state_and_no_events():
    analysis = analyze_structure([], [])
    assert analysis.state == StructureState.UNKNOWN
    assert analysis.events == []


def test_insufficient_swings_stay_unknown():
    candles = make_candles([10, 11, 12, 13, 14, 15, 14, 13])  # only one swing possible
    swings = detect_swings(candles, left_bars=2, right_bars=2)
    analysis = analyze_structure(candles, swings)
    assert analysis.state == StructureState.UNKNOWN
