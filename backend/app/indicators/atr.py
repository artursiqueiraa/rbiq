from app.data.types import Candle
from app.indicators.base import Indicator
from app.indicators.types import IndicatorResult


def true_range_series(highs: list[float], lows: list[float], closes: list[float]) -> list[float]:
    """True Range, defined and tested on its own before ATR smooths it.

    TR[0]  = high[0] - low[0]          (no previous close to compare against)
    TR[i]  = max(high[i]-low[i], abs(high[i]-close[i-1]), abs(low[i]-close[i-1]))  for i >= 1
    """
    n = len(highs)
    result: list[float] = [0.0] * n
    if n == 0:
        return result

    result[0] = highs[0] - lows[0]
    for i in range(1, n):
        result[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
    return result


def atr_series(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> list[float | None]:
    """Average True Range, Wilder's smoothing (the original definition — same
    recurrence style as RSI's average gain/loss).

    seed:       ATR[period-1] = mean(TR[0 .. period-1])
    recurrence: ATR[i] = (ATR[i-1]*(period-1) + TR[i]) / period,  for i >= period
    """
    n = len(highs)
    result: list[float | None] = [None] * n
    if period <= 0 or n < period:
        return result

    tr = true_range_series(highs, lows, closes)

    atr = sum(tr[:period]) / period
    result[period - 1] = atr

    for i in range(period, n):
        atr = (atr * (period - 1) + tr[i]) / period
        result[i] = atr

    return result


class ATR(Indicator):
    """Average True Range.

    Parameters:
        period (int > 0): default 14.

    Definition: see `true_range_series` and `atr_series`. Uses Wilder's
    smoothing, documented explicitly since "ATR" without qualification is
    ambiguous between Wilder's method and a plain SMA of True Range.

    Insufficient data: None before index period-1, and whenever fewer than
    `period` candles are provided.

    Example:
        ATR(period=14).calculate(candles) -> IndicatorResult(series={"value": [...]})
    """

    name = "ATR"

    def __init__(self, period: int = 14):
        if period <= 0:
            raise ValueError("period must be > 0")
        self.period = period

    def calculate(self, candles: list[Candle]) -> IndicatorResult:
        highs = [float(c.high) for c in candles]
        lows = [float(c.low) for c in candles]
        closes = [float(c.close) for c in candles]
        values = atr_series(highs, lows, closes, self.period)
        return IndicatorResult(name=self.name, parameters={"period": self.period}, series={"value": values})
