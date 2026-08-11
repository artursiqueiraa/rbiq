from app.data.types import Candle
from app.indicators.base import Indicator
from app.indicators.sma import sma_series
from app.indicators.types import IndicatorResult


def bollinger_series(
    values: list[float], period: int = 20, std_multiplier: float = 2.0
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Bollinger Bands.

    middle[i] = SMA(period)[i]
    std[i]    = POPULATION standard deviation of close[i-period+1 .. i]
                (divide by N, not N-1 — the standard convention in technical
                analysis; this is a deliberate choice worth flagging since
                statistics libraries often default to the sample stdev instead)
    upper[i]  = middle[i] + std_multiplier * std[i]
    lower[i]  = middle[i] - std_multiplier * std[i]

    None wherever middle is None (same window-availability policy as SMA).
    """
    middle = sma_series(values, period)
    upper: list[float | None] = [None] * len(values)
    lower: list[float | None] = [None] * len(values)

    for i, mid in enumerate(middle):
        if mid is None:
            continue
        window = values[i - period + 1 : i + 1]
        variance = sum((v - mid) ** 2 for v in window) / period
        std = variance**0.5
        upper[i] = mid + std_multiplier * std
        lower[i] = mid - std_multiplier * std

    return middle, upper, lower


class Bollinger(Indicator):
    """Bollinger Bands.

    Parameters:
        period (int > 0): default 20.
        std_multiplier (float > 0): default 2.0.

    Definition: see `bollinger_series`. Uses population standard deviation.

    Insufficient data: None for i < period-1, same as SMA (the middle band is
    literally an SMA).

    Example:
        Bollinger(period=20, std_multiplier=2).calculate(candles)
        -> IndicatorResult(series={"middle": [...], "upper": [...], "lower": [...]})
    """

    name = "BOLLINGER"

    def __init__(self, period: int = 20, std_multiplier: float = 2.0):
        if period <= 0:
            raise ValueError("period must be > 0")
        if std_multiplier <= 0:
            raise ValueError("std_multiplier must be > 0")
        self.period = period
        self.std_multiplier = std_multiplier

    def calculate(self, candles: list[Candle]) -> IndicatorResult:
        closes = [float(c.close) for c in candles]
        middle, upper, lower = bollinger_series(closes, self.period, self.std_multiplier)
        return IndicatorResult(
            name=self.name,
            parameters={"period": self.period, "std_multiplier": self.std_multiplier},
            series={"middle": middle, "upper": upper, "lower": lower},
        )
