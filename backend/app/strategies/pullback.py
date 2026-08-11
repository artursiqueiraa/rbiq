from app.strategies.base import ConditionCheck, Strategy, decide_direction
from app.strategies.context import StrategyContext
from app.strategies.types import IndicatorRequest, StrategyEvaluation


class Pullback(Strategy):
    """Looks for a temporary correction WITHIN an established trend, followed
    by a resumption of that trend — never fires mid-decline just because the
    market happens to be bullish overall (Sprint 5 section 19 explicitly
    forbids that).

    Parameters:
        pullback_ema (int > 0): reference average the pullback should
            approach. Default 20.
        lookback_candles (int > 0): how many candles back to look for the
            pullback extreme. Default 10.
        pullback_tolerance_pct (0.0-1.0): how close price needs to have come
            to the EMA, relative to the EMA's own value. Default 0.005 (0.5%).

    CALL requires (scored equally):
        - regime_compatible:        snapshot.regime in {TRENDING_BULLISH}
        - market_direction_bullish: snapshot.direction == BULLISH
        - structure_bullish:        snapshot.structure_state == BULLISH
        - pullback_touched_ema:     within the lookback window, price came
            within pullback_tolerance_pct of the EMA at some point (the
            "correction")
        - resumption_confirmed:     the CURRENT candle closes above both the
            EMA and the previous close, AND above the pullback's own low —
            i.e. price is moving back in the trend's direction, not still
            falling (this is what makes it a pullback and not a reversal)
    PUT is the exact mirror image.
    """

    name = "pullback"
    compatible_regimes = frozenset({"TRENDING_BULLISH", "TRENDING_BEARISH"})

    def default_parameters(self) -> dict:
        return {
            **super().default_parameters(),
            "pullback_ema": 20,
            "lookback_candles": 10,
            "pullback_tolerance_pct": 0.005,
        }

    def validate_parameters(self, parameters: dict) -> None:
        super().validate_parameters(parameters)
        if parameters["pullback_ema"] <= 0:
            raise ValueError("pullback_ema must be > 0")
        if parameters["lookback_candles"] <= 0:
            raise ValueError("lookback_candles must be > 0")
        if not 0.0 <= parameters["pullback_tolerance_pct"] <= 1.0:
            raise ValueError("pullback_tolerance_pct must be between 0.0 and 1.0")

    def required_indicators(self) -> list[IndicatorRequest]:
        return [IndicatorRequest("EMA", {"period": self.parameters["pullback_ema"]})]

    def evaluate(self, context: StrategyContext) -> StrategyEvaluation:
        lookback = self.parameters["lookback_candles"]
        min_len = lookback + 2  # window + a pre-window point + the resumption candle
        if len(context.candles) < min_len:
            return self._insufficient_data(context, f"need at least {min_len} candles, have {len(context.candles)}")

        ema_key = f"EMA_{self.parameters['pullback_ema']}"
        ema_series = context.indicators[ema_key].series["value"]
        closes = [float(c.close) for c in context.candles]

        window_start = len(closes) - 1 - lookback
        window_end = len(closes) - 1  # exclusive of the current (last) candle
        window_indices = range(window_start, window_end)

        if any(ema_series[i] is None for i in window_indices) or ema_series[-1] is None:
            return self._insufficient_data(context, "EMA not yet available across the lookback window")

        touched_ema = any(
            abs(closes[i] - ema_series[i]) <= self.parameters["pullback_tolerance_pct"] * ema_series[i]
            for i in window_indices
        )
        pullback_low = min(closes[i] for i in window_indices)
        pullback_high = max(closes[i] for i in window_indices)

        current_close = closes[-1]
        previous_close = closes[-2]
        current_ema = ema_series[-1]

        bullish_resumption = current_close > previous_close and current_close > current_ema and current_close > pullback_low
        bearish_resumption = current_close < previous_close and current_close < current_ema and current_close < pullback_high

        snapshot = context.market_snapshot
        bullish_checks = [
            self._regime_check(context),
            ConditionCheck("market_direction_bullish", snapshot.direction.value == "BULLISH"),
            ConditionCheck("structure_bullish", snapshot.structure_state.value == "BULLISH"),
            ConditionCheck("pullback_touched_ema", touched_ema),
            ConditionCheck("resumption_confirmed", bullish_resumption),
        ]
        bearish_checks = [
            self._regime_check(context),
            ConditionCheck("market_direction_bearish", snapshot.direction.value == "BEARISH"),
            ConditionCheck("structure_bearish", snapshot.structure_state.value == "BEARISH"),
            ConditionCheck("pullback_touched_ema", touched_ema),
            ConditionCheck("resumption_confirmed", bearish_resumption),
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
            metadata={"pullback_low": pullback_low, "pullback_high": pullback_high, "ema": current_ema},
        )
