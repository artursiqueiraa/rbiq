"""
LiveTradingLoop — o orquestrador que faltava: puxa candles reais, roda uma
estratégia do Strategy Engine (Sprint 5) a cada candle novo, e manda o sinal
resultante para o `LiveExecutor` (Sprint 7).

Mesma lógica de `app/backtest/adapters.py::StrategyEvaluatorAdapter`
(build_snapshot -> indicadores -> StrategyContext -> strategy.evaluate),
reimplementada aqui em vez de importada de `app.backtest` — a isolação entre
`app.backtest` e `app.execution` (nenhum dos dois importa o outro) é uma
regra estabelecida desde a Sprint 7; este pacote (`app.live`) fica ACIMA dos
dois, então pode depender de ambos sem violar essa regra, mas duplicar as
~15 linhas de lógica de avaliação é mais simples e mais seguro do que criar
um terceiro ponto de acoplamento entre backtest e execução.

Causalidade: cada iteração busca só os `candle_count` candles mais recentes
e reavalia a estratégia quando (e só quando) aparece um candle novo — nunca
reavalia o mesmo candle repetidamente, e nunca olha além do que a corretora
devolveu como "agora".
"""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from typing import Callable, Optional, Protocol, Sequence

from app.data.types import Candle, Timeframe
from app.execution.executor import LiveExecutor
from app.execution.types import ExecutionRecord
from app.indicators.registry import IndicatorRegistry, result_key
from app.market.snapshot import build_snapshot
from app.strategies.base import Strategy
from app.strategies.context import StrategyContext


class CandleSource(Protocol):
    def get_recent_candles(self, symbol: str, timeframe: Timeframe, count: int) -> Sequence[Candle]: ...


@dataclass
class LiveTradingLoop:
    candle_source: CandleSource
    executor: LiveExecutor
    strategy: Strategy
    symbol: str
    timeframe: Timeframe = Timeframe.M1
    candle_count: int = 200
    poll_interval_s: float = 5.0
    on_record: Callable[[ExecutionRecord], None] = field(default=lambda record: None)
    on_error: Callable[[BaseException], None] = field(default=lambda exc: None)

    _last_evaluated_timestamp: Optional[object] = field(default=None, init=False, repr=False)

    def run_once(self) -> Optional[ExecutionRecord]:
        """Uma iteração: busca candles -> avalia a estratégia -> executa se
        houver sinal. Devolve o `ExecutionRecord` produzido, ou `None` se não
        havia candle novo ou a estratégia não sinalizou nada."""
        candles = list(self.candle_source.get_recent_candles(self.symbol, self.timeframe, self.candle_count))
        if not candles:
            return None

        latest = candles[-1]
        if self._last_evaluated_timestamp is not None and latest.timestamp <= self._last_evaluated_timestamp:
            return None  # mesmo candle de antes (ainda formando) — não reavalia
        self._last_evaluated_timestamp = latest.timestamp

        snapshot = build_snapshot(candles, symbol=self.symbol, timeframe=self.timeframe)

        indicators = {}
        for spec in self.strategy.required_indicators():
            indicator = IndicatorRegistry.create(spec.name, **spec.parameters)
            result = indicator.calculate(candles)
            indicators[result_key(result)] = result

        context = StrategyContext(
            symbol=self.symbol,
            timeframe=self.timeframe,
            timestamp=latest.timestamp,
            market_snapshot=snapshot,
            candles=candles,
            indicators=indicators,
        )

        evaluation = self.strategy.evaluate(context)
        if evaluation.signal is None:
            return None

        record = self.executor.execute(evaluation.signal, symbol=self.symbol)
        self.on_record(record)
        return record

    def run_forever(self, max_iterations: Optional[int] = None, stop_event=None) -> None:
        """Nunca deixa uma falha numa única iteração matar o loop inteiro —
        mesmo princípio do `LiveExecutor.execute` (seção "nunca levanta"),
        aplicado um nível acima: um erro ao buscar candles ou avaliar a
        estratégia vira `on_error(exc)` e o loop tenta de novo na próxima
        iteração, em vez de derrubar o processo inteiro."""
        iterations = 0
        while stop_event is None or not stop_event.is_set():
            try:
                self.run_once()
            except Exception as exc:  # nunca mata o loop por uma iteração ruim
                self.on_error(exc)
                traceback.print_exc()

            iterations += 1
            if max_iterations is not None and iterations >= max_iterations:
                break

            if stop_event is not None:
                stop_event.wait(self.poll_interval_s)
            else:
                time.sleep(self.poll_interval_s)
