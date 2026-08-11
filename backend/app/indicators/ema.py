from app.data.types import Candle
from app.indicators.base import Indicator
from app.indicators.sma import sma_series
from app.indicators.types import IndicatorResult


def ema_series(values: list[float], period: int) -> list[float | None]:
    """Exponential Moving Average, seeded with a plain SMA.

    smoothing factor: alpha = 2 / (period + 1)
    seed:             EMA[period-1] = SMA(values[0 .. period-1])
    recurrence:       EMA[i] = value[i]*alpha + EMA[i-1]*(1-alpha)   for i >= period

    This is the standard seeding convention (there is no "true" EMA before
    enough data exists to average, so we bootstrap from an SMA rather than
    starting from the very first value, which would bias early results).
    `None` before the seed index.
    """
    if period <= 0 or not values:
        return [None] * len(values)

    seed = sma_series(values, period)
    result: list[float | None] = list(seed)
    alpha = 2.0 / (period + 1)

    previous: float | None = None
    for i, value in enumerate(values):
        if result[i] is not None and previous is None:
            previous = result[i]
            continue
        if previous is not None:
            current = value * alpha + previous * (1 - alpha)
            result[i] = current
            previous = current

    return result


class EMA(Indicator):
    """Exponential Moving Average.

    Parameters:
        period (int > 0): default 20.

    Definition: see `ema_series` — SMA-seeded, alpha = 2/(period+1).

    Insufficient data: None before the seed index (period-1), same policy as SMA.

    Example:
        EMA(period=20).calculate(candles) -> IndicatorResult(series={"value": [...]})
    """

    name = "EMA"

    def __init__(self, period: int = 20):
        if period <= 0:
            raise ValueError("period must be > 0")
        self.period = period

    def calculate(self, candles: list[Candle]) -> IndicatorResult:
        closes = [float(c.close) for c in candles]
        values = ema_series(closes, self.period)
        return IndicatorResult(name=self.name, parameters={"period": self.period}, series={"value": values})
