from app.strategies.base import ConditionCheck, Strategy, decide_direction
from app.strategies.context import StrategyContext
from app.strategies.types import StrategyEvaluation

ALL_NON_UNKNOWN_REGIMES = frozenset(
    {"TRENDING_BULLISH", "TRENDING_BEARISH", "RANGING", "HIGH_VOLATILITY", "LOW_VOLATILITY", "TRANSITION"}
)


def _candle_shape(candle) -> tuple[float, float, float, float]:
    """(body, upper_wick, lower_wick, range) — all in price units, all >= 0.
    A flat candle (range == 0) reports every component as 0."""
    open_, close, high, low = float(candle.open), float(candle.close), float(candle.high), float(candle.low)
    rng = high - low
    body = abs(close - open_)
    upper_wick = high - max(open_, close)
    lower_wick = min(open_, close) - low
    return body, upper_wick, lower_wick, rng


class PriceAction(Strategy):
    """The one strategy that does NOT require indicators (Sprint 5 section
    28) — it reads candle shape and the Market Engine's structure/S-R
    directly.

    Rejection candle, defined mathematically (section 29 forbids anything
    vaguer than this):
        body <= max_body_ratio * range
        (lower_wick for a bullish rejection, upper_wick for a bearish one)
            >= min_wick_ratio * range
    i.e. a small body with a long wick on the rejecting side — a classic
    pin bar / hammer shape, with the ratios configurable rather than fixed.

    Patterns implemented (two of the four the Sprint suggests — the other two,
    "rompimento estrutural" and general continuation, are already covered by
    the Market Engine's own STRUCTURE_BREAK/HIGHER_HIGH/HIGHER_LOW events,
    reused here rather than redefined):
        - support_rejection / resistance_rejection: a rejection-shaped candle
          whose low/high falls inside a Market Engine support/resistance zone
        - structural_continuation: the Market Engine's own structure state is
          already BULLISH/BEARISH and its most recent structure event is a
          HIGHER_HIGH/HIGHER_LOW (or LOWER_HIGH/LOWER_LOW) — i.e. the trend is
          actively extending, not just existing

    Parameters:
        min_wick_ratio (0.0-1.0): default 0.5.
        max_body_ratio (0.0-1.0): default 0.35.

    CALL requires (scored equally):
        - regime_compatible:  broadly permissive by default (all but UNKNOWN)
            — Price Action is explicitly "configurável" per regime (section
            36); a caller who wants it restricted passes compatible_regimes
            via a subclass or a narrower deployment, not by editing this file
        - not_against_bearish_structure: structure_state != BEARISH
        - support_rejection_or_continuation: support_rejection OR
            structural_continuation is present
    PUT is the exact mirror image.
    """

    name = "price_action"
    compatible_regimes = ALL_NON_UNKNOWN_REGIMES

    def default_parameters(self) -> dict:
        return {**super().default_parameters(), "min_wick_ratio": 0.5, "max_body_ratio": 0.35}

    def validate_parameters(self, parameters: dict) -> None:
        super().validate_parameters(parameters)
        if not 0.0 <= parameters["min_wick_ratio"] <= 1.0:
            raise ValueError("min_wick_ratio must be between 0.0 and 1.0")
        if not 0.0 <= parameters["max_body_ratio"] <= 1.0:
            raise ValueError("max_body_ratio must be between 0.0 and 1.0")

    def evaluate(self, context: StrategyContext) -> StrategyEvaluation:
        if not context.candles:
            return self._insufficient_data(context, "no candles available")

        candle = context.candles[-1]
        body, upper_wick, lower_wick, rng = _candle_shape(candle)

        if rng == 0:
            bullish_rejection_shape = bearish_rejection_shape = False
        else:
            small_body = body <= self.parameters["max_body_ratio"] * rng
            bullish_rejection_shape = small_body and lower_wick >= self.parameters["min_wick_ratio"] * rng
            bearish_rejection_shape = small_body and upper_wick >= self.parameters["min_wick_ratio"] * rng

        snapshot = context.market_snapshot
        support_touch = any(z.lower_bound <= candle.low <= z.upper_bound for z in snapshot.supports)
        resistance_touch = any(z.lower_bound <= candle.high <= z.upper_bound for z in snapshot.resistances)

        support_rejection = bullish_rejection_shape and support_touch
        resistance_rejection = bearish_rejection_shape and resistance_touch

        latest_event = snapshot.structure_events[-1] if snapshot.structure_events else None
        bullish_continuation = snapshot.structure_state.value == "BULLISH" and latest_event is not None and latest_event.event_type.value in ("HIGHER_HIGH", "HIGHER_LOW")
        bearish_continuation = snapshot.structure_state.value == "BEARISH" and latest_event is not None and latest_event.event_type.value in ("LOWER_HIGH", "LOWER_LOW")

        bullish_checks = [
            self._regime_check(context),
            ConditionCheck("not_against_bearish_structure", snapshot.structure_state.value != "BEARISH"),
            ConditionCheck("support_rejection_or_continuation", support_rejection or bullish_continuation),
        ]
        bearish_checks = [
            self._regime_check(context),
            ConditionCheck("not_against_bullish_structure", snapshot.structure_state.value != "BULLISH"),
            ConditionCheck("resistance_rejection_or_continuation", resistance_rejection or bearish_continuation),
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
                "body": body,
                "upper_wick": upper_wick,
                "lower_wick": lower_wick,
                "range": rng,
                "support_rejection": support_rejection,
                "resistance_rejection": resistance_rejection,
            },
        )
