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
import threading
import time
import types
from pathlib import Path

import pytest

from app.execution import (
    AccountType,
    BrokerConnectionError,
    BrokerRejectionError,
    Credentials,
    ExecutionStatus,
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
        self.refresh_actives_called = False
        self.refresh_actives_side_effect = None  # None | Exception | "hang"

    def connect(self):
        return self.connect_result

    def change_balance(self, mode):
        self.balance_mode = mode

    def get_balance(self):
        return self.balance

    def get_ALL_Binary_ACTIVES_OPCODE(self):
        self.refresh_actives_called = True
        if self.refresh_actives_side_effect == "hang":
            time.sleep(10.0)
            return
        if isinstance(self.refresh_actives_side_effect, Exception):
            raise self.refresh_actives_side_effect


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


def test_connect_refreshes_the_actives_list_when_the_client_supports_it(monkeypatch):
    # Achado real (validação manual, Sprint 7): sem isto, buy() recusava
    # TODA ordem binária (inclusive em ativos comprovadamente abertos) por
    # não reconhecer o símbolo — o dicionário local de ativos só vem
    # parcialmente populado até este refresh ser chamado.
    fake = _FakeIQOption("a@b.com", "x")
    _install_fake_stable_api(monkeypatch, fake)

    gateway = IQOptionGateway(Credentials(email="a@b.com", password="x"))
    gateway.connect()

    assert fake.refresh_actives_called is True


def test_connect_still_works_when_client_lacks_refresh_actives_method(monkeypatch):
    # Compatibilidade com forks que não tenham esse método específico
    # (# VERIFICAR): connect() não deve quebrar por causa disso.
    class _NoRefreshClient(_FakeIQOption):
        get_ALL_Binary_ACTIVES_OPCODE = None  # remove o atributo/método

    fake = _NoRefreshClient("a@b.com", "x")
    _install_fake_stable_api(monkeypatch, fake)

    gateway = IQOptionGateway(Credentials(email="a@b.com", password="x"))
    gateway.connect()  # não deve levantar

    assert gateway.current_account_type() is AccountType.PRACTICE


def test_connect_raises_when_refresh_actives_fails(monkeypatch):
    fake = _FakeIQOption("a@b.com", "x")
    fake.refresh_actives_side_effect = RuntimeError("falha simulada ao atualizar ativos")
    _install_fake_stable_api(monkeypatch, fake)

    gateway = IQOptionGateway(Credentials(email="a@b.com", password="x"))
    with pytest.raises(BrokerConnectionError, match="lista de ativos"):
        gateway.connect()


def test_connect_times_out_when_refresh_actives_hangs(monkeypatch):
    fake = _FakeIQOption("a@b.com", "x")
    fake.refresh_actives_side_effect = "hang"
    _install_fake_stable_api(monkeypatch, fake)

    gateway = IQOptionGateway(Credentials(email="a@b.com", password="x"), refresh_actives_timeout_s=0.05)

    started = time.monotonic()
    with pytest.raises(BrokerConnectionError, match="lista de ativos"):
        gateway.connect()
    elapsed = time.monotonic() - started

    assert elapsed < 2.0  # bem menor que os 10s que _FakeIQOption levaria


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


class _HangingClient:
    """Simula o achado real: buy()/buy_digital_spot() nunca retorna."""

    def buy(self, *args, **kwargs):
        time.sleep(10.0)
        return True, "nunca-chega-aqui"

    buy_digital_spot = buy


class _RaisingClient:
    def buy(self, *args, **kwargs):
        raise RuntimeError("falha simulada da lib")


def test_place_order_times_out_instead_of_hanging_forever():
    # Achado real (Sprint 7, validação manual em DEMO): buy_digital_spot()
    # travou de verdade por 85s+ nesse fork. place_order() precisa devolver
    # um erro em tempo limitado, nunca travar o processo indefinidamente.
    gateway = IQOptionGateway(Credentials(email="a@b.com", password="x"), place_order_timeout_s=0.05)
    gateway._client = _HangingClient()
    gateway._connected_account_type = AccountType.PRACTICE

    started = time.monotonic()
    with pytest.raises(BrokerConnectionError, match="não respondeu"):
        gateway.place_order(mk_request(account_type=AccountType.PRACTICE))
    elapsed = time.monotonic() - started

    assert elapsed < 2.0  # bem menor que os 10s que _HangingClient levaria


def test_place_order_propagates_exceptions_raised_by_the_broker_call():
    gateway = IQOptionGateway(Credentials(email="a@b.com", password="x"), place_order_timeout_s=5.0)
    gateway._client = _RaisingClient()
    gateway._connected_account_type = AccountType.PRACTICE

    with pytest.raises(RuntimeError, match="falha simulada"):
        gateway.place_order(mk_request(account_type=AccountType.PRACTICE))


def test_place_order_within_timeout_still_returns_normally():
    gateway = IQOptionGateway(Credentials(email="a@b.com", password="x"), place_order_timeout_s=5.0)
    dummy = _DummyClient()
    gateway._client = dummy
    gateway._connected_account_type = AccountType.PRACTICE

    order_id = gateway.place_order(mk_request(account_type=AccountType.PRACTICE))
    assert order_id == "order-123"


class _ResultClient:
    """Client conectado que também resolve resultados (binário e digital)."""

    def __init__(self):
        self.check_win_v4_called_with = None
        self.check_win_digital_v2_called_with = None
        self.check_win_v4_return = (None, None)
        self.check_win_digital_v2_return = (False, None)

    def buy(self, *args, **kwargs):
        return True, "222333"  # ids binários também são numéricos (check_win_v4 faz int(order_id))

    def buy_digital_spot(self, *args, **kwargs):
        return True, "555111"  # ids digitais são numéricos de verdade (check_win_digital_v2 faz int(order_id))

    def check_win_v4(self, order_id):
        self.check_win_v4_called_with = order_id
        return self.check_win_v4_return

    def check_win_digital_v2(self, order_id):
        self.check_win_digital_v2_called_with = order_id
        return self.check_win_digital_v2_return


def _gateway_with(client, **kwargs):
    gateway = IQOptionGateway(Credentials(email="a@b.com", password="x"), **kwargs)
    gateway._client = client
    gateway._connected_account_type = AccountType.PRACTICE
    return gateway


def test_await_result_routes_digital_orders_to_check_win_digital_v2_not_v4():
    # Achado real (Sprint 7): binário e digital são resolvidos por métodos
    # DIFERENTES na lib. Sem rastrear o instrumento por order_id,
    # await_result sempre chamava check_win_v4 — errado para ordens digitais,
    # que nunca resolveriam de verdade.
    client = _ResultClient()
    client.check_win_digital_v2_return = (True, 5.0)
    gateway = _gateway_with(client)

    order_id = gateway.place_order(mk_request(instrument=InstrumentType.DIGITAL))
    result = gateway.await_result(order_id, poll_interval_s=0.01, poll_timeout_s=1.0)

    assert client.check_win_digital_v2_called_with == int(order_id)
    assert client.check_win_v4_called_with is None
    assert result.status is ExecutionStatus.WON
    assert result.profit == 5.0


def test_await_result_routes_binary_orders_to_check_win_v4():
    client = _ResultClient()
    client.check_win_v4_return = ("win", 8.0)
    gateway = _gateway_with(client)

    order_id = gateway.place_order(mk_request(instrument=InstrumentType.BINARY))
    result = gateway.await_result(order_id, poll_interval_s=0.01, poll_timeout_s=1.0)

    assert client.check_win_v4_called_with == int(order_id)
    assert client.check_win_digital_v2_called_with is None
    assert result.status is ExecutionStatus.WON


@pytest.mark.parametrize(
    "profit,expected_status",
    [(5.0, ExecutionStatus.WON), (-5.0, ExecutionStatus.LOST), (0.0, ExecutionStatus.TIE)],
)
def test_await_result_digital_infers_status_from_profit_sign(profit, expected_status):
    # check_win_digital_v2 não devolve um status "win"/"loose"/"equal" como o
    # binário — só (closed, profit). WON/LOST/TIE precisam ser inferidos.
    client = _ResultClient()
    client.check_win_digital_v2_return = (True, profit)
    gateway = _gateway_with(client)

    order_id = gateway.place_order(mk_request(instrument=InstrumentType.DIGITAL))
    result = gateway.await_result(order_id, poll_interval_s=0.01, poll_timeout_s=1.0)

    assert result.status is expected_status
    assert result.profit == profit


def test_await_result_digital_check_win_hang_is_retried_not_fatal():
    # check_win_digital_v2 tem o MESMO busy-wait sem timeout que
    # buy_digital_spot (achado real). Uma única chamada travada não pode
    # virar ERROR imediato — o polling deve tratá-la como "ainda não
    # resolvido" e tentar de novo até poll_timeout_s.
    client = _ResultClient()
    calls = {"n": 0}
    hang_event = threading.Event()

    def flaky_check_win_digital_v2(order_id):
        calls["n"] += 1
        if calls["n"] == 1:
            hang_event.wait(1.0)  # trava bem além do check_win_call_timeout_s
            return False, None
        return True, 3.0

    client.check_win_digital_v2 = flaky_check_win_digital_v2
    gateway = _gateway_with(client, check_win_call_timeout_s=0.05)

    order_id = gateway.place_order(mk_request(instrument=InstrumentType.DIGITAL))
    result = gateway.await_result(order_id, poll_interval_s=0.01, poll_timeout_s=2.0)

    assert result.status is ExecutionStatus.WON
    assert result.profit == 3.0
    assert calls["n"] >= 2
