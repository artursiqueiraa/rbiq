from app.market.structure.swings import detect_swings
from app.market.types import SwingType
from app.strategies.base import ConditionCheck, Strategy, decide_direction, value_at
from app.strategies.context import StrategyContext
from app.strategies.types import IndicatorRequest, StrategyEvaluation


class Divergence(Strategy):
    """Compares price swings against an indicator's value at those SAME
    swings — using the exact same causal swing detector as the Market Engine
    (Sprint 4's detect_swings, not a new algorithm, per section 33). Applied
    directly to context.candles rather than reading MarketSnapshot's single
    latest_swing_high/low, because divergence needs to compare the two most
    recent swings of a type, not just the latest one.

    Bullish divergence: price makes a Lower Low while RSI makes a Higher Low
    at the same two swing points — momentum is fading even though price is
    still falling. This is a DIVERGENCE, not a signal by itself (section 31):
    it only becomes a CALL candidate alongside the other configured
    conditions, most importantly that the divergence is recent and that price
    has already started turning.

    Parameters:
        rsi_period (int > 0): default 14.
        left_bars / right_bars (int >= 0): same meaning as the Market Engine's
            swing detector. Default 2/2.
        max_bars_between_swings (int > 0): the more recent swing must be
            within this many candles of "now" — an old divergence is not a
            current setup. Default 30.
        require_confirmation_candle (bool): if True, also require the current
            close to already be past the divergence swing's close (price has
            started moving). Default True.

    CALL requires (scored equally):
        - regime_compatible
        - enough_swings:        at least 2 confirmed swing lows exist
        - price_lower_low:      the more recent low < the older low
        - rsi_higher_low:       RSI at the more recent low > RSI at the older low
        - divergence_recent:    the more recent low is within max_bars_between_swings
        - confirmation_candle:  current close > close at the more recent low
            (only checked when require_confirmation_candle is True)
    PUT is the exact mirror image (swing highs, Higher High + Lower High in RSI).
    """

    name = "divergence"
    compatible_regimes = frozenset({"TRENDING_BULLISH", "TRENDING_BEARISH", "RANGING", "TRANSITION"})

    def default_parameters(self) -> dict:
        return {
            **super().default_parameters(),
            "rsi_period": 14,
            "left_bars": 2,
            "right_bars": 2,
            "max_bars_between_swings": 30,
            "require_confirmation_candle": True,
        }

    def validate_parameters(self, parameters: dict) -> None:
        super().validate_parameters(parameters)
        if parameters["rsi_period"] <= 0:
            raise ValueError("rsi_period must be > 0")
        if parameters["left_bars"] < 0 or parameters["right_bars"] < 0:
            raise ValueError("left_bars and right_bars must be >= 0")
        if parameters["max_bars_between_swings"] <= 0:
            raise ValueError("max_bars_between_swings must be > 0")

    def required_indicators(self) -> list[IndicatorRequest]:
        return [IndicatorRequest("RSI", {"period": self.parameters["rsi_period"]})]

    def evaluate(self, context: StrategyContext) -> StrategyEvaluation:
        candles = context.candles
        if not candles:
            return self._insufficient_data(context, "no candles available")

        rsi_key = f"RSI_{self.parameters['rsi_period']}"
        rsi_series = context.indicators[rsi_key].series["value"]

        swings = detect_swings(candles, left_bars=self.parameters["left_bars"], right_bars=self.parameters["right_bars"])
        lows = [s for s in swings if s.type == SwingType.LOW]
        highs = [s for s in swings if s.type == SwingType.HIGH]

        last_index = len(candles) - 1
        current_close = float(candles[-1].close)

        bullish_checks = self._direction_checks(
            context, lows, rsi_series, current_close, last_index, price_lower=True
        )
        bearish_checks = self._direction_checks(
            context, highs, rsi_series, current_close, last_index, price_lower=False
        )

        direction, confidence, triggered, failed = decide_direction(
            bullish_checks, bearish_checks, min_confidence=self.parameters["min_confidence"]
        )

        return self._build_evaluation(
            context,
            direction=direction,
            confidence=confidence,
            triggered=triggered,
            failed=failed,
            metadata={"swing_lows": len(lows), "swing_highs": len(highs)},
        )

    def _direction_checks(self, context, swings, rsi_series, current_close, last_index, *, price_lower: bool):
        regime = self._regime_check(context)
        enough = len(swings) >= 2

        if not enough:
            label = "price_lower_low" if price_lower else "price_higher_high"
            rsi_label = "rsi_higher_low" if price_lower else "rsi_lower_high"
            return [
                regime,
                ConditionCheck("enough_swings", False),
                ConditionCheck(label, False),
                ConditionCheck(rsi_label, False),
                ConditionCheck("divergence_recent", False),
                ConditionCheck("confirmation_candle", False),
            ]

        older, newer = swings[-2], swings[-1]
        rsi_older = value_at(rsi_series, older.index)
        rsi_newer = value_at(rsi_series, newer.index)

        if price_lower:
            price_condition = ConditionCheck("price_lower_low", newer.price < older.price)
            rsi_ok = rsi_older is not None and rsi_newer is not None and rsi_newer > rsi_older
            rsi_condition = ConditionCheck("rsi_higher_low", rsi_ok)
            confirmation_ok = current_close > float(newer.price)
        else:
            price_condition = ConditionCheck("price_higher_high", newer.price > older.price)
            rsi_ok = rsi_older is not None and rsi_newer is not None and rsi_newer < rsi_older
            rsi_condition = ConditionCheck("rsi_lower_high", rsi_ok)
            confirmation_ok = current_close < float(newer.price)

        recent = (last_index - newer.index) <= self.parameters["max_bars_between_swings"]

        checks = [
            regime,
            ConditionCheck("enough_swings", True),
            price_condition,
            rsi_condition,
            ConditionCheck("divergence_recent", recent),
        ]
        if self.parameters["require_confirmation_candle"]:
            checks.append(ConditionCheck("confirmation_candle", confirmation_ok))
        return checks
