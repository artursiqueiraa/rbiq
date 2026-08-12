"""
Testes do IQOptionGateway que NÃO dependem de rede nem de conta real.

Cobrem: import tardio (nunca no topo do módulo), a trava 3 de 3 (conta da
sessão vs. conta da ordem), os erros de "não conectado ainda", e a detecção
de 2FA em `connect()`.

IMPORTANTE: desde que `backend/pyproject.toml` passou a apontar para o fork
mantido (`iqoptionapi @ git+.../iqoptionapi.git@7.0.0`, ver seção 8 do
relatório da Sprint 7), `stable_api.IQ_Option` existe de verdade no
ambiente — e `IQ_Option(...).connect()` faz uma chamada de rede REAL para os
servidores da IQ Option assim que é invocado, mesmo com credenciais falsas.
Por isso NENHUM teste aqui chama `gateway.connect()` sem antes substituir
`sys.modules["iqoptionapi.stable_api"]` por um dublê — os testes precisam
continuar herméticos independentemente de qual `iqoptionapi` está instalado.
(Foi rodando esta suíte pela primeira vez contra o fork real que a checagem
de 2FA abaixo pegou seu próprio falso positivo: o texto de erro real
`{"code":"invalid_credentials",...}` continha a substring "code" e disparava
`TwoFactorAuthRequired` por engano — corrigido em `iqoption.py` junto com
estes testes.)
"""

from __future__ import annotations

import ast
import sys
import types
from pathlib import Path

import pytest

from app.execution import (
    AccountType,
    BrokerConnectionError,
    BrokerRejectionError,
    Credentials,
    IQOptionGateway,
    InstrumentType,
    OrderDirection,
    OrderRequest,
    TwoFactorAuthRequired,
)

IQOPTION_MODULE = Path(__file__).resolve().parents[2] / "app" / "execution" / "iqoption.py"


class _FakeIQOption:
    """Dublê de `iqoptionapi.stable_api.IQ_Option` — nenhuma chamada de rede."""

    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.connect_result = (True, None)
        self.balance = 10_000.0
        self.balance_mode = None

    def connect(self):
        return self.connect_result

    def change_balance(self, mode):
        self.balance_mode = mode

    def get_balance(self):
        return self.balance


def _install_fake_stable_api(monkeypatch, fake_client: "_FakeIQOption | None" = None):
    """Substitui `iqoptionapi.stable_api` no sys.modules por um módulo falso
    ANTES do `connect()` fazer seu `from iqoptionapi.stable_api import
    IQ_Option` — o import tardio pega o módulo já em cache, sem tocar rede."""
    factory = (lambda email, password: fake_client) if fake_client is not None else _FakeIQOption
    fake_module = types.ModuleType("iqoptionapi.stable_api")
    fake_module.IQ_Option = factory  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "iqoptionapi.stable_api", fake_module)
    monkeypatch.setitem(sys.modules, "iqoptionapi", types.ModuleType("iqoptionapi"))


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


def test_no_top_level_import_of_iqoptionapi():
    # seção 9: o import da lib não-oficial só pode existir DENTRO de
    # connect(), nunca no topo do módulo.
    tree = ast.parse(IQOPTION_MODULE.read_text(encoding="utf-8"))
    for node in tree.body:  # só o nível do módulo, não dentro de funções
        if isinstance(node, ast.Import):
            assert not any(alias.name.startswith("iqoptionapi") for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("iqoptionapi")


def test_two_factor_auth_required_is_a_broker_connection_error():
    assert issubclass(TwoFactorAuthRequired, BrokerConnectionError)


def test_current_account_type_before_connect_raises():
    gateway = IQOptionGateway(Credentials(email="a@b.com", password="x"))
    with pytest.raises(BrokerConnectionError):
        gateway.current_account_type()


def test_get_balance_before_connect_raises():
    gateway = IQOptionGateway(Credentials(email="a@b.com", password="x"))
    with pytest.raises(BrokerConnectionError):
        gateway.get_balance()


def test_place_order_before_connect_raises():
    gateway = IQOptionGateway(Credentials(email="a@b.com", password="x"))
    with pytest.raises(BrokerConnectionError):
        gateway.place_order(mk_request())


def test_connect_raises_clear_error_when_stable_api_is_unavailable(monkeypatch):
    # Documenta o achado real da Sprint 7 (o pacote do PyPI, iqoptionapi==0.5,
    # não tem stable_api) de forma hermética: força o ImportError via
    # sys.modules em vez de depender de qual iqoptionapi está instalado
    # agora (que pode já ser o fork correto).
    monkeypatch.setitem(sys.modules, "iqoptionapi.stable_api", None)
    gateway = IQOptionGateway(Credentials(email="a@b.com", password="x"))
    with pytest.raises(BrokerConnectionError, match="stable_api"):
        gateway.connect()


def test_connect_succeeds_and_defaults_to_practice(monkeypatch):
    fake = _FakeIQOption("a@b.com", "x")
    fake.connect_result = (True, None)
    _install_fake_stable_api(monkeypatch, fake)

    gateway = IQOptionGateway(Credentials(email="a@b.com", password="x"))
    gateway.connect()

    assert gateway.current_account_type() is AccountType.PRACTICE
    assert fake.balance_mode == "PRACTICE"
    assert gateway.get_balance() == 10_000.0


def test_connect_raises_two_factor_when_reason_clearly_indicates_it(monkeypatch):
    fake = _FakeIQOption("a@b.com", "x")
    fake.connect_result = (False, "2FA verification_code required")
    _install_fake_stable_api(monkeypatch, fake)

    gateway = IQOptionGateway(Credentials(email="a@b.com", password="x"))
    with pytest.raises(TwoFactorAuthRequired):
        gateway.connect()


def test_connect_does_not_misdetect_a_generic_json_error_as_two_factor(monkeypatch):
    # Regressão: a resposta real de credenciais inválidas do fork instalado
    # é algo como '{"code":"invalid_credentials","message":"..."}' — a
    # substring "code" sozinha NÃO pode disparar TwoFactorAuthRequired.
    fake = _FakeIQOption("a@b.com", "x")
    fake.connect_result = (False, '{"code":"invalid_credentials","message":"wrong login"}')
    _install_fake_stable_api(monkeypatch, fake)

    gateway = IQOptionGateway(Credentials(email="a@b.com", password="x"))
    with pytest.raises(BrokerConnectionError) as excinfo:
        gateway.connect()
    assert not isinstance(excinfo.value, TwoFactorAuthRequired)


class _DummyClient:
    """Simula um client já conectado, sem passar pelo connect() real."""

    def __init__(self):
        self.buy_called = False

    def buy(self, *args, **kwargs):
        self.buy_called = True
        return True, "order-123"


def test_place_order_rejects_when_session_account_differs_from_request_account():
    # Trava 3 de 3 (seção 7): mesmo que a config e a guarda já tenham
    # autorizado REAL (travas 1 e 2), o gateway ainda recusa se a conta da
    # SESSÃO ativa não bater com a da ordem — checagem independente.
    gateway = IQOptionGateway(Credentials(email="a@b.com", password="x"))
    dummy = _DummyClient()
    gateway._client = dummy  # bypassa connect() real (sem rede neste teste)
    gateway._connected_account_type = AccountType.PRACTICE

    real_request = mk_request(account_type=AccountType.REAL)
    with pytest.raises(BrokerRejectionError):
        gateway.place_order(real_request)

    assert dummy.buy_called is False


def test_place_order_proceeds_when_session_account_matches_request_account():
    gateway = IQOptionGateway(Credentials(email="a@b.com", password="x"))
    dummy = _DummyClient()
    gateway._client = dummy
    gateway._connected_account_type = AccountType.PRACTICE

    order_id = gateway.place_order(mk_request(account_type=AccountType.PRACTICE))
    assert order_id == "order-123"
    assert dummy.buy_called is True
