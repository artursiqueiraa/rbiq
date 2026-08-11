import pytest

from app.indicators import ATR, CCI, EMA, MACD, RSI, SMA, Bollinger, Stochastic
from tests.indicators.conftest import make_candles

CLOSES = [10, 11, 12, 9, 13, 14, 8, 15, 16, 12]
HIGHS = [c + 1 for c in CLOSES]
LOWS = [c - 1 for c in CLOSES]

FACTORIES = [
    lambda: SMA(period=3),
    lambda: EMA(period=3),
    lambda: RSI(period=3),
    lambda: MACD(fast_period=2, slow_period=3, signal_period=2),
    lambda: Bollinger(period=3),
    lambda: ATR(period=3),
    lambda: Stochastic(k_period=3, d_period=2, smooth=1),
    lambda: CCI(period=3),
]


@pytest.mark.parametrize("factory", FACTORIES, ids=[f().name for f in FACTORIES])
def test_value_at_a_point_does_not_change_when_future_candles_are_added(factory):
    """Section 31 of the Sprint: compute up to candle C, then add D and E and
    recompute — C's value (and everything before it) must be identical either
    way. This is the concrete, executable form of "no look-ahead"."""
    all_candles = make_candles(CLOSES, highs=HIGHS, lows=LOWS)
    truncate_at = 6  # candles 0..5 ("up to C")

    result_truncated = factory().calculate(all_candles[:truncate_at])
    result_full = factory().calculate(all_candles)  # same prefix + D, E appended

    for key, truncated_values in result_truncated.series.items():
        full_values = result_full.series[key]
        for i in range(truncate_at):
            t, f = truncated_values[i], full_values[i]
            if t is None or f is None:
                assert t is f, f"{key}[{i}]: None mismatch between truncated ({t}) and full ({f}) runs"
            else:
                assert abs(t - f) < 1e-9, f"{key}[{i}]: {t} (truncated) != {f} (full) — look-ahead bug"
