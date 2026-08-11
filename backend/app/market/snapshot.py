from dataclasses import dataclass

from app.data.types import Candle, Timeframe
from app.indicators.atr import ATR
from app.indicators.ema import EMA
from app.market.regime.regime_engine import DEFAULT_SLOPE_PERIOD, compute_regime
from app.market.regime.volatility import DEFAULT_WINDOW
from app.market.structure.structure_engine import analyze_structure
from app.market.structure.support_resistance import DEFAULT_TOLERANCE_PCT, detect_zones
from app.market.structure.swings import detect_swings
from app.market.types import (
    MarketDirection,
    MarketRegime,
    MarketSnapshot,
    StructureState,
    VolatilityRegime,
    ZoneKind,
)

DEFAULT_LEFT_BARS = 2
DEFAULT_RIGHT_BARS = 2
DEFAULT_ATR_PERIOD = 14
DEFAULT_TREND_EMA_PERIOD = 20


@dataclass(frozen=True)
class MarketParams:
    left_bars: int = DEFAULT_LEFT_BARS
    right_bars: int = DEFAULT_RIGHT_BARS
    sr_tolerance_pct: float = DEFAULT_TOLERANCE_PCT
    volatility_window: int = DEFAULT_WINDOW
    trend_ema_period: int = DEFAULT_TREND_EMA_PERIOD
    trend_slope_period: int = DEFAULT_SLOPE_PERIOD
    atr_period: int = DEFAULT_ATR_PERIOD


def _empty_snapshot(symbol: str, timeframe: Timeframe, timestamp) -> MarketSnapshot:
    return MarketSnapshot(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=timestamp,
        direction=MarketDirection.UNKNOWN,
        structure_state=StructureState.UNKNOWN,
        regime=MarketRegime.UNKNOWN,
        volatility=VolatilityRegime.UNKNOWN,
        volatility_value=None,
        trend_strength=None,
        latest_swing_high=None,
        latest_swing_low=None,
        supports=[],
        resistances=[],
        structure_events=[],
    )


def build_snapshot(
    candles: list[Candle],
    *,
    symbol: str,
    timeframe: Timeframe,
    params: MarketParams = MarketParams(),
) -> MarketSnapshot:
    """Pure function: no database, no I/O. `candles` must already be the
    causally-correct set (everything up to and including "now" and nothing
    after) — that truncation is MarketService's job, not this function's.
    Given that, everything computed here — swings, structure, zones, ATR, EMA,
    regime — only ever looks at indices within `candles`, so this function is
    look-ahead safe by construction: build_snapshot(candles[:k]) never differs
    from what build_snapshot(candles) would have produced at that same point.

    Every indicator value comes from the Indicators Engine (ATR, EMA) — the
    formulas are not reimplemented here (section 33).
    """
    if not candles:
        return _empty_snapshot(symbol, timeframe, None)

    swings = detect_swings(candles, left_bars=params.left_bars, right_bars=params.right_bars)
    structure = analyze_structure(candles, swings)
    zones = detect_zones(swings, tolerance_pct=params.sr_tolerance_pct)

    atr_values = ATR(period=params.atr_period).calculate(candles).series["value"]
    ema_values = EMA(period=params.trend_ema_period).calculate(candles).series["value"]
    closes = [float(c.close) for c in candles]

    regime = compute_regime(
        structure_state=structure.state,
        atr_values=atr_values,
        ema_values=ema_values,
        closes=closes,
        volatility_window=params.volatility_window,
        trend_slope_period=params.trend_slope_period,
    )

    return MarketSnapshot(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=candles[-1].timestamp,
        direction=regime.direction,
        structure_state=structure.state,
        regime=regime.regime,
        volatility=regime.volatility,
        volatility_value=regime.volatility_value,
        trend_strength=regime.trend_strength,
        latest_swing_high=structure.confirmed_highs[-1] if structure.confirmed_highs else None,
        latest_swing_low=structure.confirmed_lows[-1] if structure.confirmed_lows else None,
        supports=[z for z in zones if z.kind == ZoneKind.SUPPORT],
        resistances=[z for z in zones if z.kind == ZoneKind.RESISTANCE],
        structure_events=structure.events,
    )
