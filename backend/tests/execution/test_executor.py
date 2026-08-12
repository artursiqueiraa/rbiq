from datetime import datetime, timezone

import pytest

from app.execution import (
    AccountType,
    ExecutionConfig,
    ExecutionGuard,
    ExecutionStatus,
    InMemoryExecutionRepository,
    InstrumentType,
    LiveExecutor,
    OrderDirection,
    PaperBroker,
)

UTC = timezone.utc


class FakeSignal:
    """Duck-typed Signal (seção 17): só `.direction` é obrigatório."""

    def __init__(self, direction, symbol=None, timestamp=None, confidence=None, strength=None):
        self.direction = direction
        self.symbol = symbol  # ignorado de propósito: o executor recebe symbol à parte
        self.timestamp = timestamp
        self.confidence = confidence
        self.strength = strength


class MalformedSignal:
    """Nem sequer tem `.direction` — simula um objeto totalmente inválido."""


def mk_executor(config=None, broker=None, repository=None, guard=None):
    config = config or ExecutionConfig(fixed_stake=10.0)
    broker = broker if broker is not None else PaperBroker(initial_balance=1000.0, seed=1)
    repository = repository or InMemoryExecutionRepository()
    guard = guard or ExecutionGuard(config)
    executor = LiveExecutor(broker=broker, guard=guard, repository=repository, config=config)
    return executor, broker, repository, guard


def test_full_pipeline_won_produces_a_saved_record():
    config = ExecutionConfig(fixed_stake=10.0)
    broker = PaperBroker(initial_balance=1000.0, win_probability=1.0, payout=0.80, seed=1)
    executor, broker, repository, guard = mk_executor(config=config, broker=broker)

    signal = FakeSignal(direction=OrderDirection.CALL, timestamp=datetime(2026, 1, 1, tzinfo=UTC))
    record = executor.execute(signal, symbol="EURUSD")

    assert record.status is ExecutionStatus.WON
    assert record.profit == pytest.approx(8.0)
    assert record.request.stake == 10.0
    assert record.broker_order_id is not None
    assert repository.get(record.id) is record


def test_full_pipeline_lost():
    config = ExecutionConfig(fixed_stake=10.0)
    broker = PaperBroker(initial_balance=1000.0, win_probability=0.0, payout=0.80, seed=1)
    executor, *_ = mk_executor(config=config, broker=broker)

    signal = FakeSignal(direction=OrderDirection.PUT, timestamp=datetime(2026, 1, 1, tzinfo=UTC))
    record = executor.execute(signal, symbol="EURUSD")

    assert record.status is ExecutionStatus.LOST
    assert record.profit == pytest.approx(-10.0)


def test_full_pipeline_tie_is_never_collapsed_into_a_boolean():
    config = ExecutionConfig(fixed_stake=10.0)
    broker = PaperBroker(initial_balance=1000.0, win_probability=0.0, tie_probability=1.0, seed=1)
    executor, *_ = mk_executor(config=config, broker=broker)

    signal = FakeSignal(direction=OrderDirection.CALL, timestamp=datetime(2026, 1, 1, tzinfo=UTC))
    record = executor.execute(signal, symbol="EURUSD")

    assert record.status is ExecutionStatus.TIE
    assert record.profit == 0.0


def test_guard_rejection_produces_rejected_record_and_never_touches_broker():
    config = ExecutionConfig(fixed_stake=10.0, kill_switch=True)
    broker = PaperBroker(initial_balance=1000.0, seed=1)
    executor, broker, repository, guard = mk_executor(config=config, broker=broker)

    signal = FakeSignal(direction=OrderDirection.CALL, timestamp=datetime(2026, 1, 1, tzinfo=UTC))
    record = executor.execute(signal, symbol="EURUSD")

    assert record.status is ExecutionStatus.REJECTED
    assert record.reject_reason == "KILL_SWITCH_ATIVO"
    assert broker.get_balance() == 1000.0  # place_order nunca foi chamado


def test_broker_connection_error_produces_error_record_without_raising():
    config = ExecutionConfig(fixed_stake=10.0)
    broker = PaperBroker(initial_balance=1000.0, seed=1)
    broker.force_connection_error = True
    executor, *_ = mk_executor(config=config, broker=broker)

    signal = FakeSignal(direction=OrderDirection.CALL, timestamp=datetime(2026, 1, 1, tzinfo=UTC))
    record = executor.execute(signal, symbol="EURUSD")

    assert record.status is ExecutionStatus.ERROR
    assert record.error is not None


def test_broker_rejection_produces_rejected_record_without_raising():
    config = ExecutionConfig(fixed_stake=10.0)
    broker = PaperBroker(initial_balance=1000.0, seed=1)
    broker.force_place_rejection = "ativo fechado no momento"
    executor, *_ = mk_executor(config=config, broker=broker)

    signal = FakeSignal(direction=OrderDirection.CALL, timestamp=datetime(2026, 1, 1, tzinfo=UTC))
    record = executor.execute(signal, symbol="EURUSD")

    assert record.status is ExecutionStatus.REJECTED
    assert record.reject_reason == "ativo fechado no momento"


def test_malformed_signal_produces_error_record_and_never_raises():
    executor, *_ = mk_executor()
    record = executor.execute(MalformedSignal(), symbol="EURUSD")
    assert record.status is ExecutionStatus.ERROR
    assert record.request is None


def test_idempotency_same_signal_never_places_a_second_order():
    config = ExecutionConfig(fixed_stake=10.0)
    broker = PaperBroker(initial_balance=1000.0, win_probability=1.0, payout=0.80, seed=1)
    executor, broker, repository, guard = mk_executor(config=config, broker=broker)

    ts = datetime(2026, 1, 1, tzinfo=UTC)
    signal = FakeSignal(direction=OrderDirection.CALL, timestamp=ts)

    first = executor.execute(signal, symbol="EURUSD")
    balance_after_first = broker.get_balance()
    second = executor.execute(signal, symbol="EURUSD")

    assert second.id == first.id
    assert broker.get_balance() == balance_after_first  # nenhuma segunda ordem foi enviada
    assert len(repository.list_all()) == 1


def test_stake_always_comes_from_config_never_from_the_signal():
    config = ExecutionConfig(fixed_stake=7.5)
    broker = PaperBroker(initial_balance=1000.0, win_probability=1.0, seed=1)
    executor, *_ = mk_executor(config=config, broker=broker)

    signal = FakeSignal(direction=OrderDirection.CALL, timestamp=datetime(2026, 1, 1, tzinfo=UTC))
    signal.stake = 999.0  # um Signal real não tem isso, mas mesmo se tivesse: é ignorado
    record = executor.execute(signal, symbol="EURUSD")

    assert record.request.stake == 7.5


def test_execution_record_never_reaches_real_account_without_dual_authorization():
    config = ExecutionConfig(fixed_stake=10.0)  # PRACTICE, sem allow_real
    broker = PaperBroker(initial_balance=1000.0, seed=1)
    executor, *_ = mk_executor(config=config, broker=broker)

    # Um Signal jamais carrega account_type — mas se algum caminho de wiring
    # tentasse forçar REAL via config adulterada em runtime, a guarda (trava
    # 2) ainda bloquearia antes do broker ser tocado.
    config.account_type = AccountType.REAL  # bypassa a trava 1 (só roda no __post_init__)
    signal = FakeSignal(direction=OrderDirection.CALL, timestamp=datetime(2026, 1, 1, tzinfo=UTC))
    record = executor.execute(signal, symbol="EURUSD")

    assert record.status is ExecutionStatus.REJECTED
    assert record.reject_reason == "CONTA_REAL_NAO_AUTORIZADA"
