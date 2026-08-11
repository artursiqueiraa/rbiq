from app.data.types import Candle
from app.indicators.base import Indicator
from app.indicators.sma import sma_series
from app.indicators.types import IndicatorResult


def stochastic_series(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    k_period: int = 14,
    d_period: int = 3,
    smooth: int = 3,
) -> tuple[list[float | None], list[float | None]]:
    """Stochastic Oscillator — the "slow" variant (raw %K is itself smoothed
    before becoming the reported %K), which is what most platforms show by
    default. Set smooth=1 to get the raw/"fast" %K unchanged.

    raw_k[i] = 100 * (close[i] - lowest_low(i-k_period+1..i)) / (highest_high(...) - lowest_low(...))
    k[i]     = SMA(smooth) applied to raw_k
    d[i]     = SMA(d_period) applied to k

    If highest_high == lowest_low in a window (a flat market), raw_k is defined
    as 50.0 (the neutral midpoint) rather than dividing by zero.
    """
    n = len(highs)
    raw_k: list[float | None] = [None] * n

    for i in range(n):
        if i < k_period - 1:
            continue
        window_high = max(highs[i - k_period + 1 : i + 1])
        window_low = min(lows[i - k_period + 1 : i + 1])
        span = window_high - window_low
        raw_k[i] = 50.0 if span == 0 else 100 * (closes[i] - window_low) / span

    k = _sma_skip_none(raw_k, smooth)
    d = _sma_skip_none(k, d_period)
    return k, d


def _sma_skip_none(values: list[float | None], period: int) -> list[float | None]:
    """SMA over a list that starts with a run of Nones — the Nones are excluded
    from the window entirely (not treated as zero), matching how MACD's signal
    line is computed over its own already-shortened series."""
    known_indices = [i for i, v in enumerate(values) if v is not None]
    known_values = [values[i] for i in known_indices]  # type: ignore[misc]
    smoothed = sma_series(known_values, period)

    result: list[float | None] = [None] * len(values)
    for position, original_index in enumerate(known_indices):
        result[original_index] = smoothed[position]
    return result


class Stochastic(Indicator):
    """Stochastic Oscillator (slow variant by default).

    Parameters:
        k_period (int > 0): lookback window for the raw %K. Default 14.
        d_period (int > 0): smoothing window for %D. Default 3.
        smooth (int > 0): smoothing window applied to raw %K before it becomes
            the reported %K. Default 3. Use 1 for the unsmoothed ("fast") %K.

    Definition: see `stochastic_series`.

    This indicator never classifies overbought/oversold — that threshold logic
    belongs to a future Strategy, not here.

    Example:
        Stochastic().calculate(candles) -> IndicatorResult(series={"k": [...], "d": [...]})
    """

    name = "STOCHASTIC"

    def __init__(self, k_period: int = 14, d_period: int = 3, smooth: int = 3):
        for label, value in (("k_period", k_period), ("d_period", d_period), ("smooth", smooth)):
            if value <= 0:
                raise ValueError(f"{label} must be > 0")
        self.k_period = k_period
        self.d_period = d_period
        self.smooth = smooth

    def calculate(self, candles: list[Candle]) -> IndicatorResult:
        highs = [float(c.high) for c in candles]
        lows = [float(c.low) for c in candles]
        closes = [float(c.close) for c in candles]
        k, d = stochastic_series(highs, lows, closes, self.k_period, self.d_period, self.smooth)
        return IndicatorResult(
            name=self.name,
            parameters={"k_period": self.k_period, "d_period": self.d_period, "smooth": self.smooth},
            series={"k": k, "d": d},
        )
