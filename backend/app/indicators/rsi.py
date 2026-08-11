from app.data.types import Candle
from app.indicators.base import Indicator
from app.indicators.types import IndicatorResult


def rsi_series(values: list[float], period: int = 14) -> list[float | None]:
    """Relative Strength Index, Wilder's original smoothing (not a plain SMA of
    gains/losses — this is the classic 1978 definition, chosen because it's the
    one virtually every charting platform means by "RSI" with no qualifier).

    deltas:  d[i] = close[i] - close[i-1],  for i >= 1
    gains:   g[i] = max(d[i], 0)
    losses:  l[i] = max(-d[i], 0)

    seed (at index = period):
        avg_gain = mean(g[1 .. period])
        avg_loss = mean(l[1 .. period])

    recurrence (i > period):
        avg_gain[i] = (avg_gain[i-1]*(period-1) + g[i]) / period
        avg_loss[i] = (avg_loss[i-1]*(period-1) + l[i]) / period

    RSI[i] = 100 - 100/(1 + avg_gain/avg_loss), with avg_loss == 0 treated as
    RSI = 100 (price only went up — the classic convention to avoid dividing by
    zero) rather than raising or returning None.

    Needs `period` deltas, i.e. `period + 1` closes, so the first non-None value
    is at index `period`.
    """
    n = len(values)
    result: list[float | None] = [None] * n
    if period <= 0 or n <= period:
        return result

    gains = [0.0] * n
    losses = [0.0] * n
    for i in range(1, n):
        delta = values[i] - values[i - 1]
        gains[i] = max(delta, 0.0)
        losses[i] = max(-delta, 0.0)

    avg_gain = sum(gains[1 : period + 1]) / period
    avg_loss = sum(losses[1 : period + 1]) / period
    result[period] = _rsi_from_averages(avg_gain, avg_loss)

    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        result[i] = _rsi_from_averages(avg_gain, avg_loss)

    return result


def _rsi_from_averages(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


class RSI(Indicator):
    """Relative Strength Index (Wilder's smoothing).

    Parameters:
        period (int > 0): default 14.

    This indicator only reports momentum strength — it never decides that
    "RSI < 30" means anything. That interpretation belongs to a future Strategy.

    Insufficient data: None for i <= period-1, and whenever fewer than
    period+1 candles are provided.

    Example:
        RSI(period=14).calculate(candles) -> IndicatorResult(series={"value": [...]})
    """

    name = "RSI"

    def __init__(self, period: int = 14):
        if period <= 0:
            raise ValueError("period must be > 0")
        self.period = period

    def calculate(self, candles: list[Candle]) -> IndicatorResult:
        closes = [float(c.close) for c in candles]
        values = rsi_series(closes, self.period)
        return IndicatorResult(name=self.name, parameters={"period": self.period}, series={"value": values})
