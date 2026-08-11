"""
Integração ponta a ponta: PostgreSQL real -> CandleRepositoryAdapter ->
BacktestRunner -> StrategyEvaluatorAdapter -> Strategy real (Sprint 5) ->
BacktestResult. Formaliza o smoke run manual descrito no passo 5 de
INTEGRACAO_CLAUDE_CODE.md e serve de teste de regressão para os dois bugs de
forma reais encontrados durante a integração (ver Sprint 6 report).
"""

from __future__ import annotations

import time
from datetime import timedelta

from app.backtest import BacktestConfig, BacktestRunner, CandleRepositoryAdapter, StrategyEvaluatorAdapter, summary_text
from app.repositories.candle_repository import CandleRepository
from app.strategies.registry import StrategyRegistry
from tests.strategies.conftest import STRONG_BULLISH_TREND
from tests.backtest.integration.conftest import TEST_SYMBOL_PREFIX, seed_candles

SYMBOL = f"{TEST_SYMBOL_PREFIX}BT_FULL"


def _build_runner(db_session, strategy_name: str, symbol: str, **strategy_params):
    strategy = StrategyRegistry.create(strategy_name, **strategy_params)
    candle_adapter = CandleRepositoryAdapter(CandleRepository(db_session))
    strategy_adapter = StrategyEvaluatorAdapter(strategy, symbol=symbol, timeframe="M1")
    return BacktestRunner(candle_repository=candle_adapter, strategy_service=strategy_adapter)


def test_full_pipeline_postgres_to_backtest_result(db_session):
    candles = seed_candles(db_session, SYMBOL, STRONG_BULLISH_TREND)
    runner = _build_runner(db_session, "trend_following", SYMBOL)

    config = BacktestConfig(
        symbol=SYMBOL,
        timeframe="M1",
        start=candles[0].timestamp,
        end=candles[-1].timestamp,
        strategy="trend_following",
        initial_balance=1000.0,
        stake=10.0,
        payout=0.80,
        expiry_candles=1,
    )

    result = runner.run(config)

    assert len(result.trades) > 0
    assert result.metrics["total_trades"] == len(result.trades)
    # Sanity: this dataset is a strong uptrend, so trend_following should
    # fire mostly CALL trades once EMA(50) has enough history.
    assert result.metrics["by_direction"]["CALL"]["trades"] >= result.metrics["by_direction"]["PUT"]["trades"]

    text_report = summary_text(result)
    assert "trend_following" in text_report
    assert SYMBOL in text_report


def test_regime_and_conditions_survive_the_real_signal_shape(db_session):
    """Regressão direta dos dois bugs corrigidos em adapters.py: sem o
    wrapper, isso quebraria com AttributeError ('list' has no 'get') ou
    ValueError (dict() de uma lista de strings)."""
    candles = seed_candles(db_session, SYMBOL, STRONG_BULLISH_TREND)
    runner = _build_runner(db_session, "trend_following", SYMBOL)

    config = BacktestConfig(
        symbol=SYMBOL,
        timeframe="M1",
        start=candles[0].timestamp,
        end=candles[-1].timestamp,
        strategy="trend_following",
        stake=10.0,
        payout=0.80,
    )

    result = runner.run(config)

    assert len(result.trades) > 0
    trade = result.trades[0]
    assert trade.regime.value == "TRENDING_BULLISH"
    assert isinstance(trade.conditions, dict)
    assert trade.conditions.get("market_direction_bullish") is True
    assert "TRENDING_BULLISH" in result.metrics["by_regime"]


def test_backtest_over_a_thousand_candles(db_session):
    """Não é uma meta de performance (o pacote entregue não pede uma) — mede e
    registra o custo real de rodar o pipeline completo (recomputar
    MarketSnapshot causal a cada candle) numa escala moderada. Ver Sprint 6
    report, seção de performance, para a extrapolação e a limitação conhecida
    de escala que isso revela para datasets muito maiores.
    """
    n = 1000
    closes = []
    price = 100.0
    direction = 1
    for i in range(n):
        price += direction * 0.5 + 0.001
        if i % 6 == 0:
            direction *= -1
        closes.append(round(price, 4))

    candles = seed_candles(db_session, SYMBOL, closes)
    runner = _build_runner(db_session, "trend_following", SYMBOL)

    config = BacktestConfig(
        symbol=SYMBOL,
        timeframe="M1",
        start=candles[0].timestamp,
        end=candles[-1].timestamp,
        strategy="trend_following",
        stake=10.0,
        payout=0.80,
    )

    started = time.perf_counter()
    result = runner.run(config)
    elapsed = time.perf_counter() - started

    print(f"\n[performance] {n} candles | trend_following backtest: {elapsed:.2f}s ({n / elapsed:.1f} candles/s)")

    assert result.metrics["total_trades"] >= 0
    # Generous ceiling: a bottleneck smoke test, not a benchmark to optimize for.
    assert elapsed < 60
