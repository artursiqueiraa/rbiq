from app.strategies.base import ConditionCheck, Strategy, decide_direction, last_value
from app.strategies.context import StrategyContext
from app.strategies.types import IndicatorRequest, StrategyEvaluation


class TrendFollowing(Strategy):
    """Looks for entries aligned with an ALREADY established trend — never
    fires on "EMA20 > EMA50" alone (Sprint 5 section 15 explicitly forbids
    that). Requires agreement between the Market Engine's own structure
    classification, its direction, the EMA crossover, and a minimum trend
    strength, all at once.

    Parameters:
        fast_ema (int > 0): default 20.
        slow_ema (int > 0): default 50.
        min_trend_strength (0.0-1.0): default 0.30 — MarketSnapshot.trend_strength
            must be at least this to count as "established" enough to follow.
        min_confidence (0.0-1.0): default 0.70 (inherited).
        expiry_candles (int > 0): default 1 (inherited).

    CALL requires, scored equally (confidence = satisfied/total):
        - regime_compatible:      snapshot.regime in {TRENDING_BULLISH}
        - market_direction_bullish: snapshot.direction == BULLISH
        - structure_bullish:      snapshot.structure_state == BULLISH
        - ema_fast_above_slow:    EMA(fast) > EMA(slow), latest values
        - trend_strength_sufficient: snapshot.trend_strength >= min_trend_strength
    PUT is the exact mirror image.
    """

    name = "trend_following"
    compatible_regimes = frozenset({"TRENDING_BULLISH", "TRENDING_BEARISH"})

    def default_parameters(self) -> dict:
        return {**super().default_parameters(), "fast_ema": 20, "slow_ema": 50, "min_trend_strength": 0.30}

    def validate_parameters(self, parameters: dict) -> None:
        super().validate_parameters(parameters)
        if parameters["fast_ema"] <= 0 or parameters["slow_ema"] <= 0:
            raise ValueError("fast_ema and slow_ema must be > 0")
        if parameters["fast_ema"] >= parameters["slow_ema"]:
            raise ValueError("fast_ema must be < slow_ema")
        if not 0.0 <= parameters["min_trend_strength"] <= 1.0:
            raise ValueError("min_trend_strength must be between 0.0 and 1.0")

    def required_indicators(self) -> list[IndicatorRequest]:
        return [
            IndicatorRequest("EMA", {"period": self.parameters["fast_ema"]}),
            IndicatorRequest("EMA", {"period": self.parameters["slow_ema"]}),
        ]

    def evaluate(self, context: StrategyContext) -> StrategyEvaluation:
        if not context.candles:
            return self._insufficient_data(context, "no candles available")

        fast_key = f"EMA_{self.parameters['fast_ema']}"
        slow_key = f"EMA_{self.parameters['slow_ema']}"
        fast = last_value(context.indicators[fast_key].series["value"])
        slow = last_value(context.indicators[slow_key].series["value"])

        if fast is None or slow is None:
            return self._insufficient_data(context, "EMA not yet available for the requested periods")

        snapshot = context.market_snapshot
        trend_strength = snapshot.trend_strength
        strength_ok = trend_strength is not None and trend_strength >= self.parameters["min_trend_strength"]

        bullish_checks = [
            self._regime_check(context),
            ConditionCheck("market_direction_bullish", snapshot.direction.value == "BULLISH"),
            ConditionCheck("structure_bullish", snapshot.structure_state.value == "BULLISH"),
            ConditionCheck("ema_fast_above_slow", fast > slow),
            ConditionCheck("trend_strength_sufficient", strength_ok),
        ]
        bearish_checks = [
            self._regime_check(context),
            ConditionCheck("market_direction_bearish", snapshot.direction.value == "BEARISH"),
            ConditionCheck("structure_bearish", snapshot.structure_state.value == "BEARISH"),
            ConditionCheck("ema_fast_below_slow", fast < slow),
            ConditionCheck("trend_strength_sufficient", strength_ok),
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
            metadata={"ema_fast": fast, "ema_slow": slow, "trend_strength": trend_strength},
        )
