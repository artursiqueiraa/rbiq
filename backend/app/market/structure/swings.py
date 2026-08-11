from app.data.types import Candle
from app.market.types import SwingPoint, SwingType


def detect_swings(candles: list[Candle], *, left_bars: int = 2, right_bars: int = 2) -> list[SwingPoint]:
    """Fractal-style swing detection with an explicit, causal confirmation delay.

    Candle i is a SWING HIGH if its high is the strict maximum among the window
    [i-left_bars, i+right_bars] (ties broken by taking the leftmost occurrence
    of the max — see `_is_center_extreme`). Candle i is a SWING LOW under the
    symmetric rule for lows.

    This is why a swing can only be *returned* once index i+right_bars is
    within the given `candles` list: confirming it requires having seen
    `right_bars` candles after it. `timestamp` on the resulting SwingPoint is
    when the extreme candle itself happened; `confirmation_timestamp` is the
    timestamp of the candle that completed the confirmation window
    (candles[i+right_bars]) — always >= timestamp, and strictly later whenever
    right_bars > 0.

    Calling this on a truncated candle list can only ever return a subset of
    what calling it on a longer list returns — swings already returned never
    change value when more candles are appended. That property is what makes
    the whole Market Engine look-ahead safe (see tests/market/test_lookahead.py
    and the Sprint 4 report).

    Parameters:
        left_bars (int >= 0): candles required before the extreme.
        right_bars (int >= 0): candles required after the extreme, i.e. the
            confirmation delay.
    """
    if left_bars < 0 or right_bars < 0:
        raise ValueError("left_bars and right_bars must be >= 0")

    n = len(candles)
    swings: list[SwingPoint] = []

    for i in range(left_bars, n - right_bars):
        window = candles[i - left_bars : i + right_bars + 1]
        center = candles[i]

        highs = [c.high for c in window]
        if _is_center_extreme(highs, left_bars, center.high, maximum=True):
            swings.append(
                SwingPoint(
                    type=SwingType.HIGH,
                    timestamp=center.timestamp,
                    confirmation_timestamp=candles[i + right_bars].timestamp,
                    price=center.high,
                    index=i,
                    strength=_strength(center.high, [c.high for c in window if c is not center], maximum=True),
                )
            )

        lows = [c.low for c in window]
        if _is_center_extreme(lows, left_bars, center.low, maximum=False):
            swings.append(
                SwingPoint(
                    type=SwingType.LOW,
                    timestamp=center.timestamp,
                    confirmation_timestamp=candles[i + right_bars].timestamp,
                    price=center.low,
                    index=i,
                    strength=_strength(center.low, [c.low for c in window if c is not center], maximum=False),
                )
            )

    return swings


def _is_center_extreme(window_values, left_bars: int, center_value, *, maximum: bool) -> bool:
    extreme = max(window_values) if maximum else min(window_values)
    if center_value != extreme:
        return False
    # Tie-break: only the leftmost occurrence of the extreme counts, so two
    # candles sharing the exact same high never both get flagged as swings.
    first_index_of_extreme = window_values.index(extreme)
    return first_index_of_extreme == left_bars


def _strength(center_value, other_values, *, maximum: bool) -> float:
    """How far the swing protrudes past its neighbors, in raw price units —
    deliberately simple and NOT normalized across assets (that belongs to the
    Market Regime layer, which has access to ATR). A swing high's strength is
    center - mean(other highs in the window); a swing low's is
    mean(other lows in the window) - center. Always >= 0 by construction,
    since the center is the (tie-broken) extreme of the window."""
    if not other_values:
        return 0.0
    average_other = float(sum(other_values)) / len(other_values)
    return float(center_value) - average_other if maximum else average_other - float(center_value)
