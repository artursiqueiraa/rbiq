from app.market.structure.structure_engine import analyze_structure
from app.market.structure.swings import detect_swings
from app.market.types import StructureEventType
from tests.market.conftest import make_candles


def test_confirmation_timestamp_is_preserved_and_differs_from_occurrence():
    """Section 43: T0..T4, a potential swing at T2, confirmation requires
    T3/T4. Not confirmed with only T0..T2; confirmed once T3/T4 exist, and the
    confirmation_timestamp is recorded as T4's timestamp — distinct from T2's
    own timestamp (when it happened)."""
    closes = [10, 11, 15, 13, 12]
    candles = make_candles(closes)

    partial = candles[:3]  # T0, T1, T2 only
    assert detect_swings(partial, left_bars=2, right_bars=2) == []

    full = candles  # T0..T4
    swings = detect_swings(full, left_bars=2, right_bars=2)
    assert len(swings) == 1

    swing = swings[0]
    assert swing.timestamp == candles[2].timestamp  # T2: when it happened
    assert swing.confirmation_timestamp == candles[4].timestamp  # T4: when confirmed
    assert swing.confirmation_timestamp > swing.timestamp


def test_structure_engine_only_emits_confirmation_events_at_or_after_confirmation_timestamp():
    closes = [10, 11, 15, 13, 12, 11, 10, 13, 16, 14, 12]
    candles = make_candles(closes)
    swings = detect_swings(candles, left_bars=2, right_bars=2)
    analysis = analyze_structure(candles, swings)

    confirmation_events = [e for e in analysis.events if e.event_type == StructureEventType.SWING_HIGH_CONFIRMED]
    for event, swing in zip(confirmation_events, [s for s in swings if s.type.value == "HIGH"]):
        assert event.confirmation_timestamp == swing.confirmation_timestamp
        assert event.timestamp == swing.timestamp
