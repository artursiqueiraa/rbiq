from decimal import Decimal

from app.strategies.base import ConditionCheck, Strategy, decide_direction
from app.strategies.context import StrategyContext
from app.strategies.types import IndicatorRequest, StrategyEvaluation


class Breakout(Strategy):
    """Detects a confirmed break of a relevant support/resistance zone (from
    the Market Engine, Sprint 4 — no zone math is reimplemented here).

    Confirmation rule, explicit per Sprint 5 section 22: a breakout requires
    the CLOSE (not just the high/low wick) of the last `confirmation_candles`
    candles to sit beyond the zone, AND the candle just before that window to
    have closed on the "wrong" side of the zone — i.e., an actual crossing
    happened inside the observed window, not a level price was already past.
    A one-candle wick through a resistance that closes back below it never
    satisfies this (the false-break case, section 24/54), because the check
    is on closes.

    Parameters:
        confirmation_candles (int > 0): default 1.
        atr_period (int > 0): default 14 — used for the volatility_expanding
            check (breakouts are more credible with expanding range).

    CALL requires (scored equally — only two checks, deliberately):
        - regime_compatible: snapshot.regime in {RANGING, HIGH_VOLATILITY, LOW_VOLATILITY, TRANSITION}
        - breakout_confirmed: a single all-or-nothing check combining THREE
            sub-conditions with AND — a resistance zone existed at/above price
            right before the window, confirmation_candles consecutive closes
            landed above it, AND the candle just before the window closed at
            or below it (an actual cross happened inside the window, not a
            level price was already past)

    `volatility_expanding` (ATR now > ATR at the start of the window) is
    reported in metadata but deliberately NOT scored: an earlier version
    scored resistance_identified/price_closed_above/prior_candle_was_below as
    three EQUAL, independent conditions — which meant a stale resistance zone
    sitting below a price that was actually breaking DOWN through a support
    could still rack up 4/5 "bullish" checks (identified + prior-was-below +
    volatility, missing only the one that actually matters) and clear the
    confidence threshold despite no bullish breakout having happened at all.
    Collapsing the three sub-conditions into one AND-ed check closes that gap:
    confirmation is binary by nature (it happened or it didn't), so it's
    scored as one thing (see the Sprint 5 report, "Problemas encontrados").
    PUT is the exact mirror image (support, closes below lower_bound).
    """

    name = "breakout"
    compatible_regimes = frozenset({"RANGING", "HIGH_VOLATILITY", "LOW_VOLATILITY", "TRANSITION"})

    def default_parameters(self) -> dict:
        return {**super().default_parameters(), "confirmation_candles": 1, "atr_period": 14}

    def validate_parameters(self, parameters: dict) -> None:
        super().validate_parameters(parameters)
        if parameters["confirmation_candles"] <= 0:
            raise ValueError("confirmation_candles must be > 0")
        if parameters["atr_period"] <= 0:
            raise ValueError("atr_period must be > 0")

    def required_indicators(self) -> list[IndicatorRequest]:
        return [IndicatorRequest("ATR", {"period": self.parameters["atr_period"]})]

    def evaluate(self, context: StrategyContext) -> StrategyEvaluation:
        n = self.parameters["confirmation_candles"]
        if len(context.candles) < n + 1:
            return self._insufficient_data(context, f"need at least {n + 1} candles, have {len(context.candles)}")

        closes = [c.close for c in context.candles]
        window = closes[-n:]
        prior = closes[-n - 1]

        atr_key = f"ATR_{self.parameters['atr_period']}"
        atr_series = context.indicators[atr_key].series["value"]
        atr_now = atr_series[-1]
        atr_before = atr_series[-n - 1] if len(atr_series) > n else None
        volatility_expanding = atr_now is not None and atr_before is not None and atr_now > atr_before

        snapshot = context.market_snapshot

        resistance = _closest_zone_below(snapshot.resistances, prior, attr="upper_bound")
        resistance_found = resistance is not None
        price_above_resistance = resistance_found and all(c > resistance.upper_bound for c in window)
        prior_below_resistance = resistance_found and prior <= resistance.upper_bound

        support = _closest_zone_above(snapshot.supports, prior, attr="lower_bound")
        support_found = support is not None
        price_below_support = support_found and all(c < support.lower_bound for c in window)
        prior_above_support = support_found and prior >= support.lower_bound

        bullish_breakout_confirmed = resistance_found and price_above_resistance and prior_below_resistance
        bearish_breakout_confirmed = support_found and price_below_support and prior_above_support

        bullish_checks = [
            self._regime_check(context),
            ConditionCheck("breakout_confirmed", bullish_breakout_confirmed),
        ]
        bearish_checks = [
            self._regime_check(context),
            ConditionCheck("breakout_confirmed", bearish_breakout_confirmed),
        ]

        direction, confidence, triggered, failed = decide_direction(
            bullish_checks, bearish_checks, min_confidence=self.parameters["min_confidence"]
        )

        return self._build_evaluation(
            context,
            direction=direction,
            confidence=confidence,
            triggered=triggered,
            failed=failed,
            metadata={
                "resistance": str(resistance.upper_bound) if resistance else None,
                "support": str(support.lower_bound) if support else None,
                "volatility_expanding": volatility_expanding,
            },
        )


def _closest_zone_below(zones, price: Decimal, *, attr: str):
    candidates = [z for z in zones if getattr(z, attr) <= price]
    if not candidates:
        return None
    return max(candidates, key=lambda z: getattr(z, attr))


def _closest_zone_above(zones, price: Decimal, *, attr: str):
    candidates = [z for z in zones if getattr(z, attr) >= price]
    if not candidates:
        return None
    return min(candidates, key=lambda z: getattr(z, attr))
