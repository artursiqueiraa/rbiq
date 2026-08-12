from datetime import datetime, timezone

import pytest

from app.execution import (
    AccountType,
    InstrumentType,
    OrderDirection,
    OrderRequest,
    compute_idempotency_key,
    normalize_order_direction,
)

UTC = timezone.utc


class _DuckDirection:
    """Simula um SignalDirection de outro Enum (duck typing por .value)."""

    def __init__(self, value):
        self.value = value


def test_normalize_accepts_enum_member():
    assert normalize_order_direction(OrderDirection.CALL) is OrderDirection.CALL


def test_normalize_accepts_plain_string():
    assert normalize_order_direction("PUT") is OrderDirection.PUT


def test_normalize_accepts_duck_typed_value():
    assert normalize_order_direction(_DuckDirection("CALL")) is OrderDirection.CALL


def test_normalize_rejects_invalid_direction():
    with pytest.raises(ValueError):
        normalize_order_direction("NONE")


def test_to_broker_string():
    assert OrderDirection.CALL.to_broker_string() == "call"
    assert OrderDirection.PUT.to_broker_string() == "put"


def test_idempotency_key_deterministic_for_same_inputs():
    ts = datetime(2026, 1, 1, tzinfo=UTC)
    k1 = compute_idempotency_key("EURUSD", ts, OrderDirection.CALL)
    k2 = compute_idempotency_key("EURUSD", ts, OrderDirection.CALL)
    assert k1 == k2


@pytest.mark.parametrize(
    "symbol,ts,direction",
    [
        ("GBPUSD", datetime(2026, 1, 1, tzinfo=UTC), OrderDirection.CALL),
        ("EURUSD", datetime(2026, 1, 2, tzinfo=UTC), OrderDirection.CALL),
        ("EURUSD", datetime(2026, 1, 1, tzinfo=UTC), OrderDirection.PUT),
    ],
)
def test_idempotency_key_differs_when_any_field_differs(symbol, ts, direction):
    base = compute_idempotency_key("EURUSD", datetime(2026, 1, 1, tzinfo=UTC), OrderDirection.CALL)
    other = compute_idempotency_key(symbol, ts, direction)
    assert base != other


def test_order_request_idempotency_key_matches_helper():
    ts = datetime(2026, 1, 1, tzinfo=UTC)
    request = OrderRequest(
        symbol="EURUSD",
        direction=OrderDirection.CALL,
        stake=10.0,
        expiry_minutes=1,
        instrument=InstrumentType.BINARY,
        account_type=AccountType.PRACTICE,
        signal_timestamp=ts,
    )
    assert request.idempotency_key == compute_idempotency_key("EURUSD", ts, OrderDirection.CALL)


def test_order_request_is_frozen():
    request = OrderRequest(
        symbol="EURUSD",
        direction=OrderDirection.CALL,
        stake=10.0,
        expiry_minutes=1,
        instrument=InstrumentType.BINARY,
        account_type=AccountType.PRACTICE,
    )
    with pytest.raises(Exception):
        request.stake = 20.0  # type: ignore[misc]
