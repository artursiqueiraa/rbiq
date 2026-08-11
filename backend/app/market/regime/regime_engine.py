from dataclasses import dataclass

from app.market.regime.classifier import classify_regime, direction_from_structure
from app.market.regime.volatility import DEFAULT_WINDOW, classify_volatility, normalized_atr_series
from app.market.types import MarketDirection, MarketRegime, StructureState, VolatilityRegime

DEFAULT_SLOPE_PERIOD = 5


@dataclass(frozen=True)
class RegimeResult:
    direction: MarketDirection
    regime: MarketRegime
    volatility: VolatilityRegime
    volatility_value: float | None
    trend_strength: float | None


def compute_trend_strength(
    ema_values: list[float | None], atr_values: list[float | None], *, slope_period: int = DEFAULT_SLOPE_PERIOD
) -> float | None:
    """How strongly price is trending, as a magnitude in [0, 1] (no sign — that
    comes from `direction` separately).

    slope = (EMA[i] - EMA[i - slope_period]) / slope_period    (price units per candle)
    trend_strength = min(1.0, abs(slope) / ATR[i])

    Dividing by ATR expresses the slope in "how many average true ranges did
    the EMA move per candle" — scale-free across assets, same reasoning as
    volatility normalization (section 25). A slope of one full ATR per candle
    is already an extreme move, so it's clipped at 1.0 rather than left
    unbounded. Returns None if there's no index with both a usable EMA value
    `slope_period` candles apart and a usable ATR value.
    """
    if slope_period <= 0:
        raise ValueError("slope_period must be > 0")

    n = len(ema_values)
    for i in range(n - 1, -1, -1):
        if ema_values[i] is None or atr_values[i] is None:
            continue
        earlier = i - slope_period
        if earlier < 0 or ema_values[earlier] is None:
            return None

        atr = atr_values[i]
        if atr == 0:
            return 0.0

        slope = (ema_values[i] - ema_values[earlier]) / slope_period
        return min(1.0, abs(slope) / atr)

    return None


def compute_regime(
    *,
    structure_state: StructureState,
    atr_values: list[float | None],
    ema_values: list[float | None],
    closes: list[float],
    volatility_window: int = DEFAULT_WINDOW,
    trend_slope_period: int = DEFAULT_SLOPE_PERIOD,
) -> RegimeResult:
    normalized_atr = normalized_atr_series(atr_values, closes)
    volatility, volatility_value = classify_volatility(normalized_atr, window=volatility_window)
    trend_strength = compute_trend_strength(ema_values, atr_values, slope_period=trend_slope_period)

    return RegimeResult(
        direction=direction_from_structure(structure_state),
        regime=classify_regime(structure_state, volatility),
        volatility=volatility,
        volatility_value=volatility_value,
        trend_strength=trend_strength,
    )
