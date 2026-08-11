from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.data.types import Candle, DataSource, Timeframe
from app.indicators.registry import IndicatorRegistry, result_key
from app.market.snapshot import build_snapshot
from app.strategies.context import StrategyContext

BASE_TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_candles(
    closes: list[float],
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    opens: list[float] | None = None,
    timeframe: Timeframe = Timeframe.M1,
    symbol: str = "TEST",
) -> list[Candle]:
    highs = highs if highs is not None else closes
    lows = lows if lows is not None else closes
    opens = opens if opens is not None else closes

    return [
        Candle(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=BASE_TS + timedelta(minutes=i),
            open=Decimal(str(opens[i])),
            high=Decimal(str(highs[i])),
            low=Decimal(str(lows[i])),
            close=Decimal(str(closes[i])),
            volume=None,
            source=DataSource.CSV,
        )
        for i in range(len(closes))
    ]


def build_context(candles, strategy, symbol: str = "TEST", timeframe: Timeframe = Timeframe.M1, timestamp=None) -> StrategyContext:
    """Builds a real StrategyContext in memory — runs the actual Market Engine
    (build_snapshot) and Indicators Engine (IndicatorRegistry) the strategy
    asked for, just without a database. Used throughout the unit tests so
    "unit" still means exercising the real pipeline, not a mock of it."""
    snapshot = build_snapshot(candles, symbol=symbol, timeframe=timeframe)
    indicators = {}
    for spec in strategy.required_indicators():
        indicator = IndicatorRegistry.create(spec.name, **spec.parameters)
        result = indicator.calculate(candles)
        indicators[result_key(result)] = result
    return StrategyContext(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=timestamp or candles[-1].timestamp,
        market_snapshot=snapshot,
        candles=candles,
        indicators=indicators,
    )


def zigzag(base: float, n_cycles: int, up_len: int, down_len: int, up_step: float, down_step: float) -> list[float]:
    """A zigzag that nets upward when up_len*up_step > down_len*down_step
    (downward if the reverse). Produces multiple swing highs/lows so the
    Market Engine's structure classifier has enough confirmed swings to
    resolve BULLISH/BEARISH rather than UNKNOWN."""
    closes = [base]
    price = base
    for _ in range(n_cycles):
        for _ in range(up_len):
            price += up_step
            closes.append(round(price, 4))
        for _ in range(down_len):
            price -= down_step
            closes.append(round(price, 4))
    return closes


# ---------------------------------------------------------------------------
# All datasets below were verified by actually running build_snapshot() and
# each strategy's evaluate() before being locked in here as fixtures — see
# the Sprint 5 report, "Problemas encontrados", for why that discipline
# matters (a Sprint 3 lesson about not trusting hand-picked data by feel).
# ---------------------------------------------------------------------------

# 71 candles -> StructureState.BULLISH, MarketDirection.BULLISH,
# MarketRegime.TRENDING_BULLISH, trend_strength ~0.41 (above the 0.30 default
# threshold), enough candles for the default EMA(50).
STRONG_BULLISH_TREND = zigzag(100, 5, 10, 4, 1.5, 1.0)

# Mirror image (reflected around the dataset's own midpoint) -> BEARISH /
# TRENDING_BEARISH, verified the same way.
_mid = (min(STRONG_BULLISH_TREND) + max(STRONG_BULLISH_TREND)) / 2
STRONG_BEARISH_TREND = [round(2 * _mid - c, 4) for c in STRONG_BULLISH_TREND]

# Two more up/down candles appended -> a resumption after a small pullback.
# Verified: Pullback(pullback_tolerance_pct=0.02) fires CALL/PUT on these.
PULLBACK_CALL_CLOSES = STRONG_BULLISH_TREND + [STRONG_BULLISH_TREND[-1] + 1.5, STRONG_BULLISH_TREND[-1] + 3.0]
PULLBACK_PUT_CLOSES = STRONG_BEARISH_TREND + [STRONG_BEARISH_TREND[-1] - 1.5, STRONG_BEARISH_TREND[-1] - 3.0]

# Repeating triangle wave -> StructureState.RANGE / MarketRegime.LOW_VOLATILITY.
# Peak at 15, trough at 10, hit three times each; resistance zone at 15.5,
# support zone at 9.5 (highs/lows default to close+/-0 unless overridden).
RANGE_WAVE = [10, 11, 12, 13, 14, 15, 14, 13, 12, 11, 10, 11, 12, 13, 14, 15, 14, 13, 12, 11, 10, 11, 12, 13, 14, 15]

# A longer version of the same wave, truncated right after a trough (instead
# of a peak) so a support-breakdown dataset starts from a realistic point.
# Verified: regime HIGH_VOLATILITY (still Breakout-compatible) at the cut.
_RANGE_WAVE_LONGER = RANGE_WAVE + [14, 13, 12, 11, 10, 11, 12, 13, 14, 15]
RANGE_ENDING_AT_TROUGH = _RANGE_WAVE_LONGER[:31]

# RANGE_WAVE + 3 closes that clear the resistance zone (15.5) — used with
# Breakout(confirmation_candles=3) so the whole 3-candle run counts as the
# confirmation window and the candle right before it (RANGE_WAVE's own last
# value, 15) is still on the "wrong" side. Verified: CALL, confidence 1.0.
BREAKOUT_CALL_CLOSES = RANGE_WAVE + [16, 18, 21]

# RANGE_ENDING_AT_TROUGH + 3 closes that clear the support zone (10) below.
# Verified: PUT, confidence 1.0, with Breakout(confirmation_candles=3).
BREAKOUT_PUT_CLOSES = RANGE_ENDING_AT_TROUGH + [9, 7, 5]

# A single candle whose HIGH pokes above the resistance zone but whose CLOSE
# stays below it — the false-break case (section 24/54). Verified: NONE.
FALSE_BREAK_CLOSES = RANGE_WAVE + [15.3]
FALSE_BREAK_HIGHS = [c + 0.5 for c in RANGE_WAVE] + [17.0]
FALSE_BREAK_LOWS = [c - 0.5 for c in RANGE_WAVE] + [15.0]

# RANGE_WAVE (minus its last 2 candles, so it doesn't end right at the peak)
# plus a dip-and-partial-recover pair: a red candle down to 7, then a green
# candle closing at 7.5. Verified: CALL (regime_compatible +
# price_near_lower_band + rejection_evidence = 3/4 -> confidence 0.75, clears
# the 0.70 default threshold even with rsi_oversold not (yet) triggered).
_MR_BASE = RANGE_WAVE[:-2]
MEAN_REVERSION_CALL_CLOSES = _MR_BASE + [7, 7.5]
MEAN_REVERSION_CALL_OPENS = _MR_BASE + [7, 7]

# Mirror image: a spike up to 18, then a red candle closing at 17.5. Verified: PUT.
MEAN_REVERSION_PUT_CLOSES = _MR_BASE + [18, 17.5]
MEAN_REVERSION_PUT_OPENS = _MR_BASE + [18, 18]

# RANGE_WAVE plus one hammer-shaped candle whose low touches the support zone
# (9.5) with a small green body and a long lower wick. Verified: CALL via
# support_rejection_or_continuation.
PRICE_ACTION_SUPPORT_REJECTION_CLOSES = RANGE_WAVE + [10.05]
PRICE_ACTION_SUPPORT_REJECTION_OPENS = RANGE_WAVE + [9.9]
PRICE_ACTION_SUPPORT_REJECTION_HIGHS = [c + 0.5 for c in RANGE_WAVE] + [10.1]
PRICE_ACTION_SUPPORT_REJECTION_LOWS = [c - 0.5 for c in RANGE_WAVE] + [9.5]

# Mirror image: a shooting-star-shaped candle whose high touches the
# resistance zone (15.5). Verified: PUT.
PRICE_ACTION_RESISTANCE_REJECTION_CLOSES = RANGE_WAVE + [14.95]
PRICE_ACTION_RESISTANCE_REJECTION_OPENS = RANGE_WAVE + [15.1]
PRICE_ACTION_RESISTANCE_REJECTION_HIGHS = [c + 0.5 for c in RANGE_WAVE] + [15.5]
PRICE_ACTION_RESISTANCE_REJECTION_LOWS = [c - 0.5 for c in RANGE_WAVE] + [14.9]
