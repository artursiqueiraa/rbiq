from app.data.types import Candle
from app.indicators.atr import ATR
from app.indicators.base import Indicator
from app.indicators.bollinger import Bollinger
from app.indicators.cci import CCI
from app.indicators.ema import EMA
from app.indicators.macd import MACD
from app.indicators.rsi import RSI
from app.indicators.sma import SMA
from app.indicators.stochastic import Stochastic
from app.indicators.types import IndicatorResult

_INDICATORS: dict[str, type[Indicator]] = {
    cls.name: cls for cls in (SMA, EMA, RSI, MACD, Bollinger, ATR, Stochastic, CCI)
}


class IndicatorRegistry:
    """Looks indicators up by name so callers (the API, the CLI, future
    strategies) never need an `if name == "SMA": ... elif name == "EMA": ...`
    chain — adding a ninth indicator only means adding it to `_INDICATORS`."""

    @staticmethod
    def get(name: str) -> type[Indicator]:
        try:
            return _INDICATORS[name.upper()]
        except KeyError:
            raise ValueError(f"unknown indicator: {name!r} (known: {sorted(_INDICATORS)})") from None

    @staticmethod
    def create(name: str, **parameters) -> Indicator:
        return IndicatorRegistry.get(name)(**parameters)

    @staticmethod
    def names() -> list[str]:
        return sorted(_INDICATORS)


def result_key(result: IndicatorResult) -> str:
    """EMA(period=20) -> "EMA_20"; MACD() -> "MACD_12_26_9". Matches the
    naming used in the /api/indicators/calculate response."""
    if not result.parameters:
        return result.name
    suffix = "_".join(str(v) for v in result.parameters.values())
    return f"{result.name}_{suffix}"


def calculate_indicators(candles: list[Candle], indicators: list[Indicator]) -> dict[str, IndicatorResult]:
    """Runs several indicators over the same candle series and keys the results
    by name+parameters, so results from different parameterizations of the same
    indicator (e.g. EMA_20 and EMA_50) don't collide."""
    return {result_key(result): result for result in (indicator.calculate(candles) for indicator in indicators)}
