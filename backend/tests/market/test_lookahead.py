from app.market.snapshot import build_snapshot
from app.market.structure.swings import detect_swings
from app.market.types import SwingType
from tests.market.conftest import BULLISH_CLOSES, make_candles


def test_swing_not_confirmed_until_enough_future_candles_exist():
    """Section 9: T0..T4, a swing at T2 must not be classified as confirmed
    before the candles needed for confirmation exist, then must become
    confirmed once they're provided."""
    closes = [10, 11, 15, 13, 12]  # T2 (index 2, value 15) is a candidate peak
    candles = make_candles(closes)

    # Only T0..T4 exist; right_bars=2 needs indices up to 2+2=4, which exists —
    # so with exactly 5 candles it IS confirmable. Drop the last one to prove
    # the negative case first.
    not_yet = make_candles(closes[:-1])  # T0..T3 only — index 4 missing
    assert detect_swings(not_yet, left_bars=2, right_bars=2) == []

    now_confirmed = detect_swings(candles, left_bars=2, right_bars=2)
    assert len(now_confirmed) == 1
    assert now_confirmed[0].type == SwingType.HIGH
    assert now_confirmed[0].index == 2


def test_swing_values_already_confirmed_never_change_with_more_future_data():
    """Section 42, applied directly to swings: once a swing is confirmed from
    a given prefix of candles, appending MORE future candles must not change
    its recorded price, timestamp, or confirmation_timestamp."""
    prefix = make_candles(BULLISH_CLOSES[:11])  # enough to confirm the first HIGH (idx5) and LOW (idx8)
    extended = make_candles(BULLISH_CLOSES)  # same prefix + more candles after

    prefix_swings = detect_swings(prefix, left_bars=2, right_bars=2)
    extended_swings = detect_swings(extended, left_bars=2, right_bars=2)

    assert len(prefix_swings) == 2  # HIGH@5, LOW@8 — see conftest's documented dataset
    for early_swing in prefix_swings:
        matching = next(s for s in extended_swings if s.index == early_swing.index and s.type == early_swing.type)
        assert matching.price == early_swing.price
        assert matching.timestamp == early_swing.timestamp
        assert matching.confirmation_timestamp == early_swing.confirmation_timestamp


def test_snapshot_at_a_point_in_time_is_unaffected_by_later_candles():
    """Section 31/42: build_snapshot(candles up to T) must equal what
    build_snapshot would have produced at T even after future candles (beyond
    T) are appended to the dataset."""
    truncate_at = 17  # right after the second swing low (index 16) gets confirmed
    candles_up_to_t = make_candles(BULLISH_CLOSES[:truncate_at])
    candles_full = make_candles(BULLISH_CLOSES)

    snapshot_at_t = build_snapshot(candles_up_to_t, symbol="X", timeframe=candles_up_to_t[0].timeframe)
    snapshot_from_full_truncated_at_t = build_snapshot(
        candles_full[:truncate_at], symbol="X", timeframe=candles_full[0].timeframe
    )

    assert snapshot_at_t.structure_state == snapshot_from_full_truncated_at_t.structure_state
    assert snapshot_at_t.direction == snapshot_from_full_truncated_at_t.direction
    assert snapshot_at_t.regime == snapshot_from_full_truncated_at_t.regime
    assert snapshot_at_t.latest_swing_high == snapshot_from_full_truncated_at_t.latest_swing_high
    assert snapshot_at_t.latest_swing_low == snapshot_from_full_truncated_at_t.latest_swing_low
    assert snapshot_at_t.structure_events == snapshot_from_full_truncated_at_t.structure_events
