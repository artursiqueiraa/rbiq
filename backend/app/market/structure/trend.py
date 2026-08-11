from enum import Enum

from app.market.types import StructureState, SwingPoint


class SwingComparison(str, Enum):
    HIGHER = "HIGHER"
    LOWER = "LOWER"
    EQUAL = "EQUAL"


def compare_swing(current: SwingPoint, previous: SwingPoint) -> SwingComparison:
    """Compares two confirmed swings of the same type (both highs or both
    lows), in chronological order. EQUAL is its own case (not folded into
    HIGHER or LOWER) because two swings at the exact same price is a real,
    if rare, edge case worth its own explicit test."""
    if current.price > previous.price:
        return SwingComparison.HIGHER
    if current.price < previous.price:
        return SwingComparison.LOWER
    return SwingComparison.EQUAL


def classify_state(confirmed_highs: list[SwingPoint], confirmed_lows: list[SwingPoint]) -> StructureState:
    """Decision tree, deterministic and documented (no ML, per the Sprint's
    explicit rule):

    1. Fewer than 2 confirmed highs OR fewer than 2 confirmed lows -> UNKNOWN
       (there's nothing to compare yet).
    2. Compare the two most recent confirmed highs (high_trend: HIGHER/LOWER/EQUAL)
       and the two most recent confirmed lows (low_trend) independently.
    3. high_trend == HIGHER and low_trend == HIGHER  -> BULLISH  (HH + HL)
    4. high_trend == LOWER  and low_trend == LOWER   -> BEARISH  (LH + LL)
    5. high_trend == EQUAL or low_trend == EQUAL      -> RANGE
       (price keeps respecting the same extreme on at least one side —
       the textbook signature of a range, not a trend or a clean reversal)
    6. Anything else (HH+LL, or LH+HL — expansion or contraction that doesn't
       fit a clean trend or a clean range) -> TRANSITION
    """
    if len(confirmed_highs) < 2 or len(confirmed_lows) < 2:
        return StructureState.UNKNOWN

    high_trend = compare_swing(confirmed_highs[-1], confirmed_highs[-2])
    low_trend = compare_swing(confirmed_lows[-1], confirmed_lows[-2])

    if high_trend == SwingComparison.HIGHER and low_trend == SwingComparison.HIGHER:
        return StructureState.BULLISH
    if high_trend == SwingComparison.LOWER and low_trend == SwingComparison.LOWER:
        return StructureState.BEARISH
    if high_trend == SwingComparison.EQUAL or low_trend == SwingComparison.EQUAL:
        return StructureState.RANGE
    return StructureState.TRANSITION
