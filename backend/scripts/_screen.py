"""Varredura de paridades compartilhada por screen_pairs.py e
run_live_bot.py: roda um backtest real (candles recém-buscados) por
combinação paridade x estratégia e devolve os resultados medidos
(win_rate, expectancy, profit_factor) — não a pontuação de confiança em
tempo real (`min_confidence`), que só filtra entradas, nunca mede
histórico."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.backtest import BacktestConfig, BacktestRunner, StrategyEvaluatorAdapter
from app.data.types import Timeframe
from app.execution.broker import BrokerConnectionError
from app.execution.iqoption import IQOptionGateway
from app.strategies.registry import StrategyRegistry
from scripts._backtest_repo import InMemoryCandleRepository
from scripts._cli_helpers import safe_print


@dataclass
class ScanResult:
    symbol: str
    strategy: str
    payout: float
    trades: int
    win_rate: Optional[float]
    expectancy: Optional[float]
    profit_factor: Optional[float]

    def line(self) -> str:
        wr = f"{self.win_rate:.1%}" if self.win_rate is not None else "—"
        pf = f"{self.profit_factor:.2f}" if self.profit_factor is not None else "—"
        exp = f"{self.expectancy:+.4f}" if self.expectancy is not None else "—"
        return (
            f"{self.symbol:14s} {self.strategy:16s} trades={self.trades:4d}  "
            f"win_rate={wr:>7s}  expectancy={exp:>9s}  profit_factor={pf:>6s}  payout={self.payout:.0%}"
        )


def scan_pairs(
    gateway: IQOptionGateway,
    strategy_names: list[str],
    candidates: list[tuple[str, float]],
    min_confidence: float,
    candle_count: int,
) -> list[ScanResult]:
    """Um backtest real por combinação (paridade, estratégia). Candles são
    buscados uma vez por paridade e reaproveitados entre as estratégias
    testadas nela. Ctrl+C interrompe e devolve o que já foi calculado até
    ali, em vez de perder tudo."""
    results: list[ScanResult] = []
    total_runs = len(candidates) * len(strategy_names)
    run_index = 0
    try:
        for symbol, payout in candidates:
            safe_print(f"Buscando candles de {symbol}...")
            try:
                candles = list(gateway.get_recent_candles(symbol, Timeframe.M1, candle_count))
            except BrokerConnectionError as exc:
                safe_print(f"  falhou ao buscar candles de {symbol}: {exc} — pulando")
                continue
            if len(candles) < 50:
                safe_print(f"  só {len(candles)} candles para {symbol} — pulando")
                continue

            repository = InMemoryCandleRepository(candles)
            for strategy_name in strategy_names:
                run_index += 1
                strategy = StrategyRegistry.create(strategy_name, min_confidence=min_confidence)
                strategy_service = StrategyEvaluatorAdapter(strategy, symbol, "M1")
                config = BacktestConfig(
                    symbol=symbol,
                    timeframe="M1",
                    start=candles[0].timestamp,
                    end=candles[-1].timestamp,
                    strategy=strategy_name,
                    initial_balance=1000.0,
                    stake=1.0,
                    payout=payout,
                    expiry_candles=1,
                )
                runner = BacktestRunner(repository, strategy_service)
                result = runner.run(config)
                m = result.metrics
                scan = ScanResult(
                    symbol=symbol,
                    strategy=strategy_name,
                    payout=payout,
                    trades=m["total_trades"],
                    win_rate=m.get("win_rate"),
                    expectancy=m.get("expectancy"),
                    profit_factor=m.get("profit_factor"),
                )
                results.append(scan)
                safe_print(f"  [{run_index}/{total_runs}] {scan.line()}")
    except KeyboardInterrupt:
        safe_print("\nInterrompido — mantendo o que já foi calculado até aqui.\n")
    return results


def rank_by_expectancy(results: list[ScanResult], min_trades: int) -> list[ScanResult]:
    """Descarta amostras pequenas demais para significar algo e ordena as
    demais da melhor para a pior expectancy (retorno esperado por trade,
    já ponderando win_rate e payout — mais informativo que win_rate
    isolado para decidir onde operar)."""
    significant = [r for r in results if r.trades >= min_trades]
    significant.sort(key=lambda r: (r.expectancy if r.expectancy is not None else float("-inf")), reverse=True)
    return significant
