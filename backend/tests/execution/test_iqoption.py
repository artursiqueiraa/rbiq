"""
Testes do IQOptionGateway que NÃO dependem de rede nem de conta real.

Cobrem: import tardio (nunca no topo do módulo), a trava 3 de 3 (conta da
sessão vs. conta da ordem), e os erros de "não conectado ainda". O teste de
`connect()` roda contra o pacote `iqoptionapi` de fato instalado neste
projeto (PyPI, versão antiga sem `stable_api`) — ele documenta, em código, o
achado real registrado no relatório da Sprint 7: essa dependência precisa
ser trocada por uma fork mantida antes de qualquer validação em conta DEMO.
"""

from __future__ import annotations

import ast
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


def test_connect_fails_clearly_against_the_currently_installed_iqoptionapi_package():
    # Achado real (não simulado): o pacote iqoptionapi instalado via PyPI
    # neste projeto não expõe stable_api.IQ_Option. connect() precisa
    # detectar isso e falhar com uma mensagem acionável, não com um
    # ImportError cru vazando de dentro da lib de terceiros.
    gateway = IQOptionGateway(Credentials(email="a@b.com", password="x"))
    with pytest.raises(BrokerConnectionError, match="stable_api"):
        gateway.connect()


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
