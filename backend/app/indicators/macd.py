from app.data.types import Candle
from app.indicators.base import Indicator
from app.indicators.ema import ema_series
from app.indicators.types import IndicatorResult


def macd_series(
    values: list[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """MACD.

    macd_line[i]  = EMA(fast_period)[i] - EMA(slow_period)[i]
    signal[i]     = EMA(signal_period) applied to the macd_line's own values
                    (the signal line only exists where macd_line exists — it is
                    computed over that shorter series, not over the original
                    prices)
    histogram[i]  = macd_line[i] - signal[i]

    None wherever either operand is None.
    """
    ema_fast = ema_series(values, fast_period)
    ema_slow = ema_series(values, slow_period)

    macd_line: list[float | None] = [
        (f - s) if f is not None and s is not None else None for f, s in zip(ema_fast, ema_slow)
    ]

    # ema_series needs a densely-populated list with no gaps to seed correctly,
    # so the signal line is computed over the compacted (index -> value) subset
    # of macd_line and then scattered back into a full-length array.
    known_indices = [i for i, v in enumerate(macd_line) if v is not None]
    known_values = [macd_line[i] for i in known_indices]
    signal_known = ema_series(known_values, signal_period)

    signal: list[float | None] = [None] * len(values)
    for position, original_index in enumerate(known_indices):
        signal[original_index] = signal_known[position]

    histogram: list[float | None] = [
        (m - s) if m is not None and s is not None else None for m, s in zip(macd_line, signal)
    ]

    return macd_line, signal, histogram


class MACD(Indicator):
    """Moving Average Convergence Divergence.

    Parameters:
        fast_period (int > 0): default 12.
        slow_period (int > 0): default 26.
        signal_period (int > 0): default 9.

    Definition: see `macd_series`.

    Insufficient data: None wherever the underlying EMAs are None — see EMA's
    own docstring for that policy.

    Example:
        MACD().calculate(candles) -> IndicatorResult(series={"macd": [...], "signal": [...], "histogram": [...]})
    """

    name = "MACD"

    def __init__(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9):
        for label, value in (("fast_period", fast_period), ("slow_period", slow_period), ("signal_period", signal_period)):
            if value <= 0:
                raise ValueError(f"{label} must be > 0")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

    def calculate(self, candles: list[Candle]) -> IndicatorResult:
        closes = [float(c.close) for c in candles]
        macd_line, signal, histogram = macd_series(closes, self.fast_period, self.slow_period, self.signal_period)
        return IndicatorResult(
            name=self.name,
            parameters={
                "fast_period": self.fast_period,
                "slow_period": self.slow_period,
                "signal_period": self.signal_period,
            },
            series={"macd": macd_line, "signal": signal, "histogram": histogram},
        )
