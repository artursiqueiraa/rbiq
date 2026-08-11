from app.data.types import Candle
from app.indicators.base import Indicator
from app.indicators.sma import sma_series
from app.indicators.types import IndicatorResult

LAMBERT_CONSTANT = 0.015


def cci_series(highs: list[float], lows: list[float], closes: list[float], period: int = 20) -> list[float | None]:
    """Commodity Channel Index (Lambert's original definition).

    typical_price[i] = (high[i] + low[i] + close[i]) / 3
    sma_tp[i]         = SMA(period) of typical_price
    mean_deviation[i] = mean(|typical_price[j] - sma_tp[i]|  for j in the same window)
    CCI[i]            = (typical_price[i] - sma_tp[i]) / (0.015 * mean_deviation[i])

    0.015 is Lambert's constant, chosen so ~70-80% of values fall within [-100, 100]
    for a roughly normal price distribution — it is a fixed constant, not a
    parameter, in every standard definition of CCI.

    If mean_deviation is 0 (a perfectly flat window), CCI is defined as 0.0
    rather than dividing by zero.
    """
    n = len(highs)
    result: list[float | None] = [None] * n
    if period <= 0 or n < period:
        return result

    typical_price = [(highs[i] + lows[i] + closes[i]) / 3 for i in range(n)]
    sma_tp = sma_series(typical_price, period)

    for i, mean_price in enumerate(sma_tp):
        if mean_price is None:
            continue
        window = typical_price[i - period + 1 : i + 1]
        mean_deviation = sum(abs(v - mean_price) for v in window) / period
        if mean_deviation == 0:
            result[i] = 0.0
        else:
            result[i] = (typical_price[i] - mean_price) / (LAMBERT_CONSTANT * mean_deviation)

    return result


class CCI(Indicator):
    """Commodity Channel Index.

    Parameters:
        period (int > 0): default 20.

    Definition: see `cci_series`.

    Insufficient data: None for i < period-1, and whenever fewer than `period`
    candles are provided.

    Example:
        CCI(period=20).calculate(candles) -> IndicatorResult(series={"value": [...]})
    """

    name = "CCI"

    def __init__(self, period: int = 20):
        if period <= 0:
            raise ValueError("period must be > 0")
        self.period = period

    def calculate(self, candles: list[Candle]) -> IndicatorResult:
        highs = [float(c.high) for c in candles]
        lows = [float(c.low) for c in candles]
        closes = [float(c.close) for c in candles]
        values = cci_series(highs, lows, closes, self.period)
        return IndicatorResult(name=self.name, parameters={"period": self.period}, series={"value": values})
