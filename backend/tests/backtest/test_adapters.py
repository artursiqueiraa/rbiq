"""
Testes dos adapters de integração (app/backtest/adapters.py) — não fazem
parte do pacote entregue, escritos durante a integração desta Sprint.

Cobrem especificamente os dois bugs de forma reais encontrados no smoke run
manual (ver docs/sprints/SPRINT_6_REPORT.md, "Problemas encontrados"): o
`Signal` real usa `conditions: list[str]` e não tem `.regime`, mas
`engine.py` (um dos 13 módulos entregues, não alterado) espera `conditions`
como dict e checa `.regime` para classificar o trade por regime.
"""

from __future__ import annotations

from datetime import timedelta

from app.backtest.adapters import StrategyEvaluatorAdapter
from app.backtest.types import SignalDirection as BacktestSignalDirection
from app.data.types import Timeframe
from app.strategies.registry import StrategyRegistry
from tests.strategies.conftest import STRONG_BULLISH_TREND, make_candles


def test_evaluator_adapter_wraps_signal_with_dict_conditions_and_regime():
    """O Signal real tem conditions:list[str] e não tem .regime — o wrapper do
    adapter precisa expor .conditions como dict e .regime a partir do
    MarketSnapshot, sem o que engine.py quebra (ver Sprint 6 report)."""
    candles = make_candles(STRONG_BULLISH_TREND)
    strategy = StrategyRegistry.create("trend_following")
    adapter = StrategyEvaluatorAdapter(strategy, symbol="TEST", timeframe="M1")

    signal = adapter.evaluate(candles, {})

    assert signal is not None
    assert signal.direction == BacktestSignalDirection.CALL
    assert isinstance(signal.conditions, dict)
    assert signal.conditions.get("market_direction_bullish") is True
    assert signal.regime is not None
    assert signal.regime.value == "TRENDING_BULLISH"


def test_evaluator_adapter_returns_none_when_strategy_has_no_signal():
    # RANGE_WAVE-shaped data is not a trend_following regime -> no signal.
    from tests.strategies.conftest import RANGE_WAVE

    candles = make_candles(RANGE_WAVE)
    strategy = StrategyRegistry.create("trend_following", fast_ema=3, slow_ema=5)
    adapter = StrategyEvaluatorAdapter(strategy, symbol="TEST", timeframe="M1")

    assert adapter.evaluate(candles, {}) is None


def test_evaluator_adapter_only_sees_the_candles_it_is_given():
    """Causalidade do adapter: passar um prefixo menor produz um snapshot
    calculado só sobre esse prefixo — nada é buscado por conta própria."""
    full = make_candles(STRONG_BULLISH_TREND)
    prefix = full[:10]

    strategy = StrategyRegistry.create("trend_following", fast_ema=3, slow_ema=5)
    adapter = StrategyEvaluatorAdapter(strategy, symbol="TEST", timeframe="M1")

    signal = adapter.evaluate(prefix, {})
    # Com só 10 candles o EMA(5) já existe, mas a estrutura ainda não tem
    # swings suficientes para um regime de tendência -> sem sinal.
    assert signal is None


def test_evaluator_adapter_empty_candles_returns_none():
    strategy = StrategyRegistry.create("trend_following")
    adapter = StrategyEvaluatorAdapter(strategy, symbol="TEST", timeframe="M1")
    assert adapter.evaluate([], {}) is None
