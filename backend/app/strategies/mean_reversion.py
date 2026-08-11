from app.strategies.base import ConditionCheck, Strategy, decide_direction, last_value
from app.strategies.context import StrategyContext
from app.strategies.types import IndicatorRequest, StrategyEvaluation


class MeanReversion(Strategy):
    """Looks for price that has stretched away from a statistical reference
    (Bollinger Bands) with momentum evidence (RSI) AND actual rejection —
    never fires on "RSI < 30" alone (Sprint 5 section 26 explicitly forbids
    that). Restricted to ranging regimes (section 25): a stretched price in a
    real trend is not a mean-reversion setup.

    Parameters:
        bollinger_period (int > 0): default 20.
        bollinger_std (float > 0): default 2.0.
        rsi_period (int > 0): default 14.
        rsi_oversold (0-100): default 30.
        rsi_overbought (0-100): default 70.

    CALL requires (scored equally):
        - regime_compatible:     snapshot.regime in {RANGING, LOW_VOLATILITY, HIGH_VOLATILITY}
            (the three regimes the Market Engine derives from a RANGE
            structure state — see compatible_regimes)
        - price_near_lower_band: close <= Bollinger lower band
        - rsi_oversold:          RSI <= rsi_oversold
        - rejection_evidence:    current candle closed green AND above the
            previous close (an actual bounce, not just "the RSI is low")
    PUT is the exact mirror image (upper band, overbought, red candle).
    """

    name = "mean_reversion"
    # All three regimes the Market Engine derives from a RANGE structure state
    # (RANGING itself, plus its LOW/HIGH_VOLATILITY variants — see Sprint 4's
    # classify_regime) count as "consolidation" for this strategy's purposes;
    # volatility level alone shouldn't gate a mean-reversion setup out.
    compatible_regimes = frozenset({"RANGING", "LOW_VOLATILITY", "HIGH_VOLATILITY"})

    def default_parameters(self) -> dict:
        return {
            **super().default_parameters(),
            "bollinger_period": 20,
            "bollinger_std": 2.0,
            "rsi_period": 14,
            "rsi_oversold": 30.0,
            "rsi_overbought": 70.0,
        }

    def validate_parameters(self, parameters: dict) -> None:
        super().validate_parameters(parameters)
        if parameters["bollinger_period"] <= 0 or parameters["rsi_period"] <= 0:
            raise ValueError("bollinger_period and rsi_period must be > 0")
        if parameters["bollinger_std"] <= 0:
            raise ValueError("bollinger_std must be > 0")
        if not 0 <= parameters["rsi_oversold"] < parameters["rsi_overbought"] <= 100:
            raise ValueError("rsi_oversold must be < rsi_overbought, both within [0, 100]")

    def required_indicators(self) -> list[IndicatorRequest]:
        return [
            IndicatorRequest("BOLLINGER", {"period": self.parameters["bollinger_period"], "std_multiplier": self.parameters["bollinger_std"]}),
            IndicatorRequest("RSI", {"period": self.parameters["rsi_period"]}),
        ]

    def evaluate(self, context: StrategyContext) -> StrategyEvaluation:
        if len(context.candles) < 2:
            return self._insufficient_data(context, "need at least 2 candles")

        bollinger_key = f"BOLLINGER_{self.parameters['bollinger_period']}_{self.parameters['bollinger_std']}"
        rsi_key = f"RSI_{self.parameters['rsi_period']}"

        lower = last_value(context.indicators[bollinger_key].series["lower"])
        upper = last_value(context.indicators[bollinger_key].series["upper"])
        rsi = last_value(context.indicators[rsi_key].series["value"])

        if lower is None or upper is None or rsi is None:
            return self._insufficient_data(context, "Bollinger/RSI not yet available")

        current = context.candles[-1]
        previous = context.candles[-2]
        current_close = float(current.close)

        bullish_rejection = current.close > current.open and current.close > previous.close
        bearish_rejection = current.close < current.open and current.close < previous.close

        snapshot = context.market_snapshot
        bullish_checks = [
            self._regime_check(context),
            ConditionCheck("price_near_lower_band", current_close <= lower),
            ConditionCheck("rsi_oversold", rsi <= self.parameters["rsi_oversold"]),
            ConditionCheck("rejection_evidence", bullish_rejection),
        ]
        bearish_checks = [
            self._regime_check(context),
            ConditionCheck("price_near_upper_band", current_close >= upper),
            ConditionCheck("rsi_overbought", rsi >= self.parameters["rsi_overbought"]),
            ConditionCheck("rejection_evidence", bearish_rejection),
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
            metadata={"bollinger_lower": lower, "bollinger_upper": upper, "rsi": rsi, "regime": snapshot.regime.value},
        )
