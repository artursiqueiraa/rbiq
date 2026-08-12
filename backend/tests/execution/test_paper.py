import pytest

from app.execution import (
    AccountType,
    BrokerConnectionError,
    BrokerRejectionError,
    ExecutionStatus,
    InstrumentType,
    OrderDirection,
    OrderRequest,
    PaperBroker,
)


def mk_request(**overrides):
    base = dict(
        symbol="EURUSD",
        direction=OrderDirection.CALL,
        stake=10.0,
        expiry_minutes=1,
        instrument=InstrumentType.BINARY,
        account_type=AccountType.PRACTICE,
    )
    base.update(overrides)
    return OrderRequest(**base)


def test_current_account_type_is_always_practice():
    broker = PaperBroker()
    assert broker.current_account_type() is AccountType.PRACTICE


def test_forced_connection_error_is_raised_by_connect():
    broker = PaperBroker()
    broker.force_connection_error = True
    with pytest.raises(BrokerConnectionError):
        broker.connect()


def test_place_order_debits_balance():
    broker = PaperBroker(initial_balance=100.0, seed=1)
    broker.connect()
    broker.place_order(mk_request(stake=10.0))
    assert broker.get_balance() == 90.0


def test_place_order_rejects_when_stake_exceeds_balance():
    broker = PaperBroker(initial_balance=5.0, seed=1)
    broker.connect()
    with pytest.raises(BrokerRejectionError):
        broker.place_order(mk_request(stake=10.0))


def test_forced_place_rejection():
    broker = PaperBroker(seed=1)
    broker.connect()
    broker.force_place_rejection = "ativo fechado"
    with pytest.raises(BrokerRejectionError):
        broker.place_order(mk_request())


def test_await_result_all_wins_when_win_probability_is_one():
    broker = PaperBroker(initial_balance=100.0, win_probability=1.0, payout=0.80, seed=1)
    broker.connect()
    order_id = broker.place_order(mk_request(stake=10.0))
    result = broker.await_result(order_id, poll_interval_s=0.01, poll_timeout_s=1.0)
    assert result.status is ExecutionStatus.WON
    assert result.profit == pytest.approx(8.0)
    assert broker.get_balance() == pytest.approx(100.0 - 10.0 + 10.0 + 8.0)


def test_await_result_all_losses_when_win_probability_is_zero():
    broker = PaperBroker(initial_balance=100.0, win_probability=0.0, payout=0.80, seed=1)
    broker.connect()
    order_id = broker.place_order(mk_request(stake=10.0))
    result = broker.await_result(order_id, poll_interval_s=0.01, poll_timeout_s=1.0)
    assert result.status is ExecutionStatus.LOST
    assert result.profit == pytest.approx(-10.0)
    assert broker.get_balance() == pytest.approx(90.0)  # stake não devolvido


def test_await_result_ties_when_tie_probability_is_one():
    broker = PaperBroker(initial_balance=100.0, win_probability=0.0, tie_probability=1.0, seed=1)
    broker.connect()
    order_id = broker.place_order(mk_request(stake=10.0))
    result = broker.await_result(order_id, poll_interval_s=0.01, poll_timeout_s=1.0)
    assert result.status is ExecutionStatus.TIE
    assert result.profit == 0.0
    assert broker.get_balance() == pytest.approx(100.0)  # stake devolvido, sem lucro


def test_await_result_with_unknown_order_id_returns_error_status():
    broker = PaperBroker()
    result = broker.await_result("nao-existe", poll_interval_s=0.01, poll_timeout_s=1.0)
    assert result.status is ExecutionStatus.ERROR
    assert result.error is not None


def test_win_plus_tie_probability_over_one_is_rejected():
    with pytest.raises(ValueError):
        PaperBroker(win_probability=0.7, tie_probability=0.5)
