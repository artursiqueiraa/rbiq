from datetime import datetime, timezone

import pytest

from app.execution import (
    AccountType,
    ExecutionConfig,
    ExecutionGuard,
    GuardState,
    InstrumentType,
    OrderDirection,
    OrderRequest,
)

UTC = timezone.utc


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


class FakeClock:
    def __init__(self, start: datetime):
        self.now = start

    def __call__(self) -> datetime:
        return self.now


def test_normal_request_within_limits_is_allowed():
    cfg = ExecutionConfig(fixed_stake=10.0)
    guard = ExecutionGuard(cfg)
    decision = guard.check(mk_request())
    assert decision.allowed is True
    assert decision.reason is None


def test_kill_switch_rejects_everything():
    cfg = ExecutionConfig(fixed_stake=10.0, kill_switch=True)
    guard = ExecutionGuard(cfg)
    decision = guard.check(mk_request())
    assert decision.allowed is False
    assert decision.reason == "KILL_SWITCH_ATIVO"


def test_kill_switch_takes_effect_immediately_without_recreating_guard():
    cfg = ExecutionConfig(fixed_stake=10.0)
    guard = ExecutionGuard(cfg)
    assert guard.check(mk_request()).allowed is True
    cfg.kill_switch = True
    assert guard.check(mk_request()).allowed is False


def test_real_order_rejected_when_config_is_practice():
    # Trava 2 de 3: independente da trava 1 em ExecutionConfig.__post_init__.
    cfg = ExecutionConfig(fixed_stake=10.0)  # PRACTICE
    guard = ExecutionGuard(cfg)
    real_request = mk_request(account_type=AccountType.REAL)
    decision = guard.check(real_request)
    assert decision.allowed is False
    assert decision.reason == "CONTA_REAL_NAO_AUTORIZADA"


def test_real_order_allowed_when_config_authorizes_real():
    cfg = ExecutionConfig(account_type=AccountType.REAL, allow_real=True, fixed_stake=10.0)
    guard = ExecutionGuard(cfg)
    decision = guard.check(mk_request(account_type=AccountType.REAL))
    assert decision.allowed is True


def test_stake_must_match_fixed_stake_exactly():
    cfg = ExecutionConfig(fixed_stake=10.0)
    guard = ExecutionGuard(cfg)
    decision = guard.check(mk_request(stake=20.0))
    assert decision.allowed is False
    assert decision.reason == "STAKE_DIVERGENTE_DO_FIXO_CONFIGURADO"


def test_max_daily_trades_blocks_after_limit():
    cfg = ExecutionConfig(fixed_stake=10.0, max_daily_trades=2)
    guard = ExecutionGuard(cfg)
    guard.record_placed()
    guard.record_resolved(1.0)
    guard.record_placed()
    guard.record_resolved(1.0)
    decision = guard.check(mk_request())
    assert decision.allowed is False
    assert decision.reason == "LIMITE_DIARIO_DE_TRADES_ATINGIDO"


def test_max_daily_loss_blocks_after_limit():
    cfg = ExecutionConfig(fixed_stake=10.0, max_daily_loss=15.0)
    guard = ExecutionGuard(cfg)
    guard.record_placed()
    guard.record_resolved(-20.0)
    decision = guard.check(mk_request())
    assert decision.allowed is False
    assert decision.reason == "LIMITE_DIARIO_DE_PERDA_ATINGIDO"


def test_max_concurrent_orders_blocks_new_orders_while_one_open():
    cfg = ExecutionConfig(fixed_stake=10.0, max_concurrent_orders=1)
    guard = ExecutionGuard(cfg)
    guard.record_placed()  # 1 ordem aberta
    decision = guard.check(mk_request())
    assert decision.allowed is False
    assert decision.reason == "LIMITE_DE_ORDENS_CONCORRENTES_ATINGIDO"
    guard.record_resolved(1.0)  # fecha a ordem
    assert guard.check(mk_request()).allowed is True


def test_daily_counters_reset_on_new_day_but_open_orders_do_not():
    clock = FakeClock(datetime(2026, 1, 1, 23, 0, tzinfo=UTC))
    cfg = ExecutionConfig(fixed_stake=10.0, max_daily_trades=1, max_concurrent_orders=5)
    guard = ExecutionGuard(cfg, state=GuardState(), clock=clock)

    guard.record_placed()
    decision_same_day = guard.check(mk_request())
    assert decision_same_day.allowed is False  # limite diário batido

    clock.now = datetime(2026, 1, 2, 0, 5, tzinfo=UTC)
    decision_next_day = guard.check(mk_request())
    assert decision_next_day.allowed is True  # contador diário resetou
    assert guard.state.open_orders == 1  # mas a ordem aberta continua contando
