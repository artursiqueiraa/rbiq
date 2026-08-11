from app.data.types import Candle
from app.indicators.base import Indicator
from app.indicators.types import IndicatorResult


def sma_series(values: list[float], period: int) -> list[float | None]:
    """Simple Moving Average: value[i] is the mean of the `period` values ending
    at i. `None` for any i where fewer than `period` values are available —
    never a partially-averaged or extrapolated number."""
    result: list[float | None] = [None] * len(values)
    window_sum = 0.0

    for i, value in enumerate(values):
        window_sum += value
        if i >= period:
            window_sum -= values[i - period]
        if i >= period - 1:
            result[i] = window_sum / period

    return result


class SMA(Indicator):
    """Simple Moving Average.

    Parameters:
        period (int > 0): number of candles averaged. Default 20.

    Definition:
        SMA[i] = mean(close[i-period+1 .. i])

    Insufficient data: None for i < period-1, and for any input shorter than
    `period` candles.

    Example:
        SMA(period=20).calculate(candles) -> IndicatorResult(series={"value": [...]})
    """

    name = "SMA"

    def __init__(self, period: int = 20):
        if period <= 0:
            raise ValueError("period must be > 0")
        self.period = period

    def calculate(self, candles: list[Candle]) -> IndicatorResult:
        closes = [float(c.close) for c in candles]
        values = sma_series(closes, self.period)
        return IndicatorResult(name=self.name, parameters={"period": self.period}, series={"value": values})
