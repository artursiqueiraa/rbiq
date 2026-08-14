"""
PullbackZones — evolução do Pullback (`pullback.py`) trocando a referência
de "onde a correção tocou" de uma EMA por uma zona de suporte/resistência
FORTE (Market Engine, Sprint 4 — `Zone.strength = touches * (1 + recência)`),
e adicionando um filtro de volatilidade a partir de
`MarketSnapshot.volatility` (já derivado do ATR normalizado pelo Market
Engine — não precisa de um indicador próprio).

Pedido explícito do usuário depois de rodar o screener contra a conta real:
"pullback com zonas fortes, retração a favor da tendência, volatilidade da
vela". "Retração a favor da tendência" já é a definição central do
`Pullback` original — o que faltava era usar zonas reais (não uma média
móvel) e considerar volatilidade antes de disparar.
"""

from app.market.types import VolatilityRegime, Zone
from app.strategies.base import ConditionCheck, Strategy, decide_direction
from app.strategies.context import StrategyContext
from app.strategies.types import IndicatorRequest, StrategyEvaluation


class PullbackZones(Strategy):
    """Mesma ideia do `Pullback` (correção temporária DENTRO de uma tendência
    já estabelecida, seguida de retomada na direção da tendência — nunca
    dispara no meio de uma queda só porque o mercado é "geralmente" de
    alta), com duas mudanças:

    1. A correção precisa ter tocado uma zona de suporte/resistência FORTE
       (Market Engine, Sprint 4), não apenas se aproximado de uma EMA — uma
       zona testada várias vezes recentemente é um nível que o mercado já
       demonstrou respeitar, diferente de uma média móvel genérica.
    2. Exige volatilidade não-baixa (`MarketSnapshot.volatility`, derivado do
       ATR normalizado) — evita disparar em mercado morto/lateral, onde o
       "rompimento de volta" é só ruído sem força nenhuma por trás.

    Parameters:
        lookback_candles (int > 0): candles pra trás pra procurar o toque na
            zona (a "correção"). Default 10.
        zone_tolerance_pct (0.0-1.0): quão perto do preço da zona conta como
            "tocou", relativo ao próprio preço da zona. Default 0.002 (0.2%).
        min_zone_strength (float >= 0): força mínima da zona (toques x
            recência) pra contar como "forte". Default 1.5.
        require_elevated_volatility (bool): se True, rejeita quando
            `MarketSnapshot.volatility` é LOW. Default True.

    CALL requer (pontuado igualmente):
        - regime_compatible:            snapshot.regime in {TRENDING_BULLISH}
        - market_direction_bullish:     snapshot.direction == BULLISH
        - structure_bullish:            snapshot.structure_state == BULLISH
        - pullback_near_strong_support: dentro do lookback, o preço chegou
            perto (zone_tolerance_pct) de uma zona SUPPORT com
            strength >= min_zone_strength
        - resumption_confirmed:         candle atual fecha acima do close
            anterior E acima da mínima da correção
        - volatility_acceptable:        snapshot.volatility != LOW (se
            require_elevated_volatility=True) — sempre True caso contrário
    PUT é o espelho exato (resistência em vez de suporte, closes abaixo).
    """

    name = "pullback_zones"
    compatible_regimes = frozenset({"TRENDING_BULLISH", "TRENDING_BEARISH"})

    def default_parameters(self) -> dict:
        return {
            **super().default_parameters(),
            "lookback_candles": 10,
            "zone_tolerance_pct": 0.002,
            "min_zone_strength": 1.5,
            "require_elevated_volatility": True,
        }

    def validate_parameters(self, parameters: dict) -> None:
        super().validate_parameters(parameters)
        if parameters["lookback_candles"] <= 0:
            raise ValueError("lookback_candles must be > 0")
        if not 0.0 <= parameters["zone_tolerance_pct"] <= 1.0:
            raise ValueError("zone_tolerance_pct must be between 0.0 and 1.0")
        if parameters["min_zone_strength"] < 0:
            raise ValueError("min_zone_strength must be >= 0")

    def required_indicators(self) -> list[IndicatorRequest]:
        return []  # zonas e volatilidade já vêm prontas no MarketSnapshot

    @staticmethod
    def _touched_strong_zone(zones: list[Zone], window_prices: list[float], tolerance_pct: float, min_strength: float) -> bool:
        for zone in zones:
            if zone.strength < min_strength:
                continue
            zone_price = float(zone.price)
            if any(abs(p - zone_price) <= tolerance_pct * zone_price for p in window_prices):
                return True
        return False

    def evaluate(self, context: StrategyContext) -> StrategyEvaluation:
        lookback = self.parameters["lookback_candles"]
        min_len = lookback + 2  # janela + ponto pré-janela + o candle de retomada
        if len(context.candles) < min_len:
            return self._insufficient_data(context, f"need at least {min_len} candles, have {len(context.candles)}")

        closes = [float(c.close) for c in context.candles]
        window_start = len(closes) - 1 - lookback
        window_end = len(closes) - 1  # exclusivo do candle atual (o último)
        window_prices = closes[window_start:window_end]

        snapshot = context.market_snapshot
        tolerance = self.parameters["zone_tolerance_pct"]
        min_strength = self.parameters["min_zone_strength"]

        touched_support = self._touched_strong_zone(snapshot.supports, window_prices, tolerance, min_strength)
        touched_resistance = self._touched_strong_zone(snapshot.resistances, window_prices, tolerance, min_strength)

        pullback_low = min(window_prices)
        pullback_high = max(window_prices)
        current_close = closes[-1]
        previous_close = closes[-2]

        bullish_resumption = current_close > previous_close and current_close > pullback_low
        bearish_resumption = current_close < previous_close and current_close < pullback_high

        volatility_ok = (
            snapshot.volatility != VolatilityRegime.LOW if self.parameters["require_elevated_volatility"] else True
        )

        bullish_checks = [
            self._regime_check(context),
            ConditionCheck("market_direction_bullish", snapshot.direction.value == "BULLISH"),
            ConditionCheck("structure_bullish", snapshot.structure_state.value == "BULLISH"),
            ConditionCheck("pullback_near_strong_support", touched_support),
            ConditionCheck("resumption_confirmed", bullish_resumption),
            ConditionCheck("volatility_acceptable", volatility_ok),
        ]
        bearish_checks = [
            self._regime_check(context),
            ConditionCheck("market_direction_bearish", snapshot.direction.value == "BEARISH"),
            ConditionCheck("structure_bearish", snapshot.structure_state.value == "BEARISH"),
            ConditionCheck("pullback_near_strong_resistance", touched_resistance),
            ConditionCheck("resumption_confirmed", bearish_resumption),
            ConditionCheck("volatility_acceptable", volatility_ok),
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
                "pullback_low": pullback_low,
                "pullback_high": pullback_high,
                "volatility": snapshot.volatility.value,
            },
        )
