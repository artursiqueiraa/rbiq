"""
Testes de `LiveTradingLoop` — hermético, sem rede: candles vêm de um dublê
local (`_FakeCandleSource`), execução real vem de `PaperBroker` (Sprint 7).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.data.types import Timeframe
from app.execution.config import ExecutionConfig
from app.execution.executor import LiveExecutor
from app.execution.guard import ExecutionGuard
from app.execution.repository import InMemoryExecutionRepository
from app.execution.paper import PaperBroker
from app.live.loop import LiveTradingLoop
from app.strategies.base import Strategy
from app.strategies.types import Signal, SignalDirection, SignalStrength, StrategyEvaluation

from tests.strategies.conftest import make_candles


class _FakeCandleSource:
    """Devolve uma sequência pré-definida de "estados de mercado" — cada
    chamada a get_recent_candles() avança para o próximo lote, simulando
    novos candles chegando com o tempo."""

    def __init__(self, batches):
        self._batches = list(batches)
        self._index = 0
        self.call_count = 0

    def get_recent_candles(self, symbol, timeframe, count):
        self.call_count += 1
        if not self._batches:
            return []
        idx = min(self._index, len(self._batches) - 1)
        self._index += 1
        return self._batches[idx]


class _RaisingCandleSource:
    def get_recent_candles(self, symbol, timeframe, count):
        raise RuntimeError("falha simulada ao buscar candles")


class _FakeStrategy(Strategy):
    name = "fake"

    def __init__(self, signals=None, **kwargs):
        super().__init__(**kwargs)
        self._signals = list(signals or [])
        self.evaluate_call_count = 0

    def evaluate(self, context) -> StrategyEvaluation:
        self.evaluate_call_count += 1
        signal = self._signals.pop(0) if self._signals else None
        return StrategyEvaluation(
            strategy=self.name,
            signal=signal,
            triggered_conditions=[],
            failed_conditions=[],
            evaluated_at=datetime.now(timezone.utc),
        )


def mk_signal(direction=SignalDirection.CALL, timestamp=None) -> Signal:
    ts = timestamp or datetime(2026, 1, 1, tzinfo=timezone.utc)
    return Signal(
        id=f"sig-{ts.isoformat()}-{direction.value}",
        strategy="fake",
        symbol="TEST",
        timeframe=Timeframe.M1,
        timestamp=ts,
        direction=direction,
        strength=SignalStrength.STRONG,
        confidence=0.9,
        expiry_candles=1,
        conditions=["fake_condition"],
    )


def mk_executor(broker=None, guard=None):
    config = ExecutionConfig(fixed_stake=10.0)
    broker = broker or PaperBroker(initial_balance=1000.0, win_probability=1.0, seed=1)
    repository = InMemoryExecutionRepository()
    guard = guard or ExecutionGuard(config)
    executor = LiveExecutor(broker=broker, guard=guard, repository=repository, config=config)
    return executor, broker, repository


def test_run_once_returns_none_without_candles():
    strategy = _FakeStrategy()
    executor, *_ = mk_executor()
    loop = LiveTradingLoop(
        candle_source=_FakeCandleSource([]), executor=executor, strategy=strategy, symbol="TEST"
    )
    assert loop.run_once() is None
    assert strategy.evaluate_call_count == 0


def test_run_once_returns_none_when_strategy_does_not_signal():
    candles = make_candles([1, 2, 3, 4, 5])
    strategy = _FakeStrategy(signals=[None])
    executor, *_ = mk_executor()
    loop = LiveTradingLoop(
        candle_source=_FakeCandleSource([candles]), executor=executor, strategy=strategy, symbol="TEST"
    )
    assert loop.run_once() is None
    assert strategy.evaluate_call_count == 1


def test_run_once_skips_reevaluation_when_candle_has_not_advanced():
    candles = make_candles([1, 2, 3, 4, 5])
    strategy = _FakeStrategy(signals=[None, None])
    executor, *_ = mk_executor()
    source = _FakeCandleSource([candles, candles])  # mesmo último timestamp nas duas vezes
    loop = LiveTradingLoop(candle_source=source, executor=executor, strategy=strategy, symbol="TEST")

    loop.run_once()
    loop.run_once()

    assert strategy.evaluate_call_count == 1  # segunda chamada não reavaliou
    assert source.call_count == 2  # mas ainda buscou candles nas duas vezes


def test_run_once_executes_when_strategy_signals_and_calls_on_record():
    candles = make_candles([1, 2, 3, 4, 5])
    signal = mk_signal(timestamp=candles[-1].timestamp)
    strategy = _FakeStrategy(signals=[signal])
    executor, broker, repository = mk_executor()

    records = []
    loop = LiveTradingLoop(
        candle_source=_FakeCandleSource([candles]),
        executor=executor,
        strategy=strategy,
        symbol="TEST",
        on_record=records.append,
    )

    record = loop.run_once()

    assert record is not None
    assert record.status.value == "WON"  # win_probability=1.0 no PaperBroker
    assert records == [record]
    assert len(repository.list_all()) == 1


def test_run_once_calls_on_signal_before_on_record_with_the_full_evaluation():
    candles = make_candles([1, 2, 3, 4, 5])
    signal = mk_signal(timestamp=candles[-1].timestamp)
    strategy = _FakeStrategy(signals=[signal])
    executor, *_ = mk_executor()

    order: list[str] = []
    seen_evaluations = []
    loop = LiveTradingLoop(
        candle_source=_FakeCandleSource([candles]),
        executor=executor,
        strategy=strategy,
        symbol="TEST",
        on_signal=lambda evaluation: (order.append("signal"), seen_evaluations.append(evaluation)),
        on_record=lambda record: order.append("record"),
    )

    loop.run_once()

    assert order == ["signal", "record"]  # avaliação explicada ANTES da execução
    assert len(seen_evaluations) == 1
    assert seen_evaluations[0].signal is signal

    loop.run_once()  # mesmo candle: nada novo, nenhuma chamada extra
    assert order == ["signal", "record"]


def test_run_once_does_not_call_on_signal_when_strategy_does_not_signal():
    candles = make_candles([1, 2, 3, 4, 5])
    strategy = _FakeStrategy(signals=[None])
    executor, *_ = mk_executor()

    seen = []
    loop = LiveTradingLoop(
        candle_source=_FakeCandleSource([candles]),
        executor=executor,
        strategy=strategy,
        symbol="TEST",
        on_signal=seen.append,
    )

    loop.run_once()

    assert seen == []


def test_run_once_advances_when_a_genuinely_new_candle_arrives():
    first_batch = make_candles([1, 2, 3, 4, 5])
    second_batch = make_candles([1, 2, 3, 4, 5, 6])  # um candle a mais
    strategy = _FakeStrategy(signals=[None, None])
    executor, *_ = mk_executor()
    source = _FakeCandleSource([first_batch, second_batch])
    loop = LiveTradingLoop(candle_source=source, executor=executor, strategy=strategy, symbol="TEST")

    loop.run_once()
    loop.run_once()

    assert strategy.evaluate_call_count == 2  # candle novo -> reavaliou de verdade


def test_run_forever_stops_after_max_iterations():
    candles = make_candles([1, 2, 3])
    strategy = _FakeStrategy()
    executor, *_ = mk_executor()
    source = _FakeCandleSource([candles])
    loop = LiveTradingLoop(
        candle_source=source, executor=executor, strategy=strategy, symbol="TEST", poll_interval_s=0.01
    )

    loop.run_forever(max_iterations=3)

    assert source.call_count == 3


def test_run_forever_survives_exceptions_and_calls_on_error():
    strategy = _FakeStrategy()
    executor, *_ = mk_executor()
    errors = []
    loop = LiveTradingLoop(
        candle_source=_RaisingCandleSource(),
        executor=executor,
        strategy=strategy,
        symbol="TEST",
        poll_interval_s=0.01,
        on_error=errors.append,
    )

    loop.run_forever(max_iterations=3)  # não pode levantar

    assert len(errors) == 3
    assert all(isinstance(e, RuntimeError) for e in errors)
