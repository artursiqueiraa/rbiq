import pytest

from app.execution import AccountType, Credentials, ExecutionConfig, RealAccountNotAllowedError


def test_default_account_type_is_practice():
    cfg = ExecutionConfig(fixed_stake=10.0)
    assert cfg.account_type is AccountType.PRACTICE
    assert cfg.allow_real is False
    assert cfg.is_real_account is False


def test_real_without_allow_real_is_rejected_at_construction():
    # Trava 1 de 3 (seção 7): a config nem chega a existir em estado REAL
    # sem allow_real explícito.
    with pytest.raises(RealAccountNotAllowedError):
        ExecutionConfig(account_type=AccountType.REAL, fixed_stake=10.0)


def test_real_with_allow_real_is_accepted():
    cfg = ExecutionConfig(account_type=AccountType.REAL, allow_real=True, fixed_stake=10.0)
    assert cfg.is_real_account is True


def test_allow_real_alone_without_account_type_real_does_not_flip_is_real_account():
    cfg = ExecutionConfig(allow_real=True, fixed_stake=10.0)
    assert cfg.is_real_account is False


@pytest.mark.parametrize(
    "kwargs",
    [
        {"fixed_stake": 0},
        {"fixed_stake": -5},
        {"expiry_minutes": 0},
        {"max_concurrent_orders": 0},
        {"poll_interval_s": 0},
        {"poll_timeout_s": 0},
    ],
)
def test_invalid_numeric_fields_rejected(kwargs):
    base = {"fixed_stake": 10.0}
    base.update(kwargs)
    with pytest.raises(ValueError):
        ExecutionConfig(**base)


def test_poll_interval_cannot_exceed_poll_timeout():
    with pytest.raises(ValueError):
        ExecutionConfig(fixed_stake=10.0, poll_interval_s=100.0, poll_timeout_s=10.0)


def test_kill_switch_can_be_toggled_on_an_existing_config_instance():
    cfg = ExecutionConfig(fixed_stake=10.0)
    assert cfg.kill_switch is False
    cfg.kill_switch = True
    assert cfg.kill_switch is True


def test_credentials_from_env_reads_expected_variables(monkeypatch):
    monkeypatch.setenv("IQOPTION_EMAIL", "trader@example.com")
    monkeypatch.setenv("IQOPTION_PASSWORD", "s3cr3t")
    creds = Credentials.from_env()
    assert creds.email == "trader@example.com"
    assert creds.password == "s3cr3t"


def test_credentials_from_env_raises_when_missing(monkeypatch):
    monkeypatch.delenv("IQOPTION_EMAIL", raising=False)
    monkeypatch.delenv("IQOPTION_PASSWORD", raising=False)
    with pytest.raises(RuntimeError):
        Credentials.from_env()


def test_credentials_repr_and_str_never_leak_the_password():
    creds = Credentials(email="trader@example.com", password="s3cr3t")
    assert "s3cr3t" not in repr(creds)
    assert "s3cr3t" not in str(creds)
