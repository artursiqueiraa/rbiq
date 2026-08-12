"""
IQOptionGateway — adapter real para a IQ Option (Sprint 7, passo 9, por
último e de propósito: "correção e segurança antes de tocar em conta real").

AVISO (documentado, não removido): `iqoptionapi` é uma biblioteca
NÃO-OFICIAL e engenharia-reversa. Várias forks se descrevem como "ONLY FOR
STUDY - Don't use on your real Account". A API varia entre forks/versões sem
aviso prévio — por isso toda chamada da lib abaixo carrega um comentário
`# VERIFICAR` documentando a assinatura ESPERADA, que pode já estar errada
para a versão efetivamente instalada.

ACHADO DE INTEGRAÇÃO (real, não hipotético — documentado também no relatório
da Sprint 7): o pacote publicado no PyPI sob o nome `iqoptionapi` (versão
0.5, a que `uv add iqoptionapi` instala) é uma implementação antiga e de
baixo nível — só expõe `api.py`, com `login()`/`buy()` enviando mensagens de
websocket cruas, sem `get_balance()`, sem `change_balance()`, sem
`stable_api.py`. A imensa maioria das forks ativas usadas na comunidade
expõe `iqoptionapi.stable_api.IQ_Option`, com `connect()`, `get_balance()`,
`change_balance()`, `buy()`, `check_win_v4()`, `buy_digital_spot()` — é
contra ESSA interface que este gateway é escrito, porque é dela que uma
integração real precisa. `connect()` detecta a ausência de `stable_api` e
levanta um erro acionável em vez de falhar de forma confusa mais adiante.
Trocar a dependência por uma fork mantida que exponha `stable_api.IQ_Option`
é uma decisão do operador — este código não adiciona uma URL de fork por
conta própria.

2FA: NÃO é resolvido automaticamente dentro deste fluxo. Se o login exigir
verificação em duas etapas, `connect()` levanta `TwoFactorAuthRequired` e
para — a resolução (inserir o código, confirmar o dispositivo) precisa
acontecer numa sessão pré-autenticada separada, fora do loop de trading.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Optional

from .broker import BrokerConnectionError, BrokerGateway, BrokerRejectionError
from .config import Credentials
from .types import AccountType, ExecutionResult, ExecutionStatus, InstrumentType, OrderRequest


class TwoFactorAuthRequired(BrokerConnectionError):
    """Login exige 2FA. Por especificação, isto nunca é automatizado dentro
    do loop de trading — resolva fora deste fluxo, numa sessão à parte."""


class IQOptionGateway(BrokerGateway):
    def __init__(
        self,
        credentials: Credentials,
        practice_by_default: bool = True,
        place_order_timeout_s: float = 15.0,
        check_win_call_timeout_s: float = 5.0,
    ) -> None:
        self._credentials = credentials
        self._practice_by_default = practice_by_default
        self._place_order_timeout_s = place_order_timeout_s
        self._check_win_call_timeout_s = check_win_call_timeout_s
        self._client: Any = None
        self._connected_account_type: Optional[AccountType] = None
        # order_id -> instrument da ordem: `await_result` recebe só o
        # broker_order_id (contrato de BrokerGateway, seção 6), mas opção
        # digital e binária são resolvidas por métodos DIFERENTES na lib
        # (check_win_v4 vs check_win_digital_v2) — sem isto, uma ordem
        # digital seria consultada com o método errado e nunca resolveria.
        self._order_instruments: dict[str, InstrumentType] = {}

    def _call_with_timeout(self, timeout_s: float, fn: Callable[..., Any], *args: Any) -> Any:
        """Roda `fn(*args)` numa thread daemon, com timeout próprio.

        Achado real (Sprint 7, validação manual em DEMO): pelo menos dois
        métodos do fork instalado (`buy_digital_spot` e `check_win_digital_v2`)
        têm um busy-wait interno SEM timeout, esperando a corretora
        confirmar algo — se ela nunca confirmar (ex.: ativo fechado, ou uma
        falha de callback do websocket), a chamada trava para sempre, ANTES
        de `poll_timeout_s` sequer entrar em jogo. Confirmado na prática:
        `buy_digital_spot` não retornou em 85s reais contra a conta do
        usuário; a leitura do código-fonte de `check_win_digital_v2` mostra
        o mesmíssimo padrão (`while ...== {}: pass`).

        Não existe como matar uma thread Python à força. Se o timeout
        estourar, a thread de origem continua rodando em segundo plano
        (marcada `daemon=True` só para não impedir o processo de encerrar) e
        seu resultado, se algum dia chegar, é descartado — o chamador já
        seguiu em frente tratando isso como `BrokerConnectionError`: o
        resultado real fica DESCONHECIDO, não confirmado nem recusado. É uma
        mitigação, não uma cura — a causa raiz é um bug do fork de
        terceiros, fora do nosso controle. Quando usado dentro do polling de
        `await_result`, uma chamada que estoura esse timeout pode deixar um
        thread "zumbi" rodando por chamada — aceitável para o caso raro,
        não para o caminho feliz (onde a chamada retorna rápido)."""
        outcome: dict[str, Any] = {}

        def _run() -> None:
            try:
                outcome["value"] = fn(*args)
            except Exception as exc:  # repassado à thread principal via dict
                outcome["error"] = exc

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        thread.join(timeout_s)

        if thread.is_alive():
            raise BrokerConnectionError(
                f"Chamada à corretora não respondeu em {timeout_s}s "
                "(timeout de proteção interno do gateway). O resultado real é "
                "DESCONHECIDO — pode ter sido confirmado ou não; não assuma nenhum dos dois."
            )
        if "error" in outcome:
            raise outcome["error"]
        return outcome["value"]

    def connect(self) -> None:
        # Import tardio, de propósito — NUNCA no topo do módulo (seção 9):
        # isola o resto do sistema de uma dependência não-oficial que pode
        # nem sequer importar com sucesso, e evita pagar esse custo/risco em
        # qualquer processo que não faça execução real (testes, API, etc.
        # nunca importam `app.execution.iqoption`).
        try:
            from iqoptionapi.stable_api import IQ_Option  # type: ignore  # VERIFICAR: caminho do módulo varia por fork
        except ImportError as exc:
            raise BrokerConnectionError(
                "iqoptionapi.stable_api.IQ_Option não encontrado no pacote instalado. "
                "O pacote 'iqoptionapi' publicado no PyPI (o que 'uv add iqoptionapi' instala "
                "hoje, versão 0.5) é uma implementação antiga e de baixo nível, sem essa "
                "interface. Instale manualmente uma fork mantida que exponha "
                "stable_api.IQ_Option antes de usar IQOptionGateway."
            ) from exc

        # VERIFICAR: assinatura esperada IQ_Option(email: str, password: str).
        client = IQ_Option(self._credentials.email, self._credentials.password)

        # VERIFICAR: connect() costuma devolver (bool, motivo_ou_None); em
        # algumas forks devolve só bool. Confirme na fork instalada.
        check, reason = client.connect()
        if not check:
            reason_text = str(reason or "").lower()
            # VERIFICAR: os tokens abaixo são um palpite razoável, não uma
            # lista oficial — a fork instalada pode usar outro texto/código
            # para 2FA. Propositalmente restritivo: tokens genéricos como
            # "code" sozinho geram falso positivo (respostas de erro comuns
            # como {"code":"invalid_credentials",...} também contêm "code").
            two_factor_markers = ("2fa", "two-factor", "two_factor", "two factor", "verification_code", "verification code")
            if any(marker in reason_text for marker in two_factor_markers):
                raise TwoFactorAuthRequired(
                    f"Login exige verificação em duas etapas ({reason!r}). Resolva numa "
                    "sessão separada, pré-autenticada — esta chamada não tenta submeter "
                    "código de verificação."
                )
            raise BrokerConnectionError(f"Falha ao conectar na IQ Option: {reason!r}")

        # PRACTICE é o default em toda parte do sistema (seção 7) — mudar
        # para REAL exige `practice_by_default=False` explícito na
        # construção deste gateway, o que por sua vez só é útil se
        # ExecutionConfig/ExecutionGuard já autorizaram REAL (travas 1 e 2).
        # VERIFICAR: change_balance() aceita "PRACTICE"/"REAL" maiúsculo em
        # algumas forks, "practice"/"real" minúsculo em outras.
        target_mode = "PRACTICE" if self._practice_by_default else "REAL"
        client.change_balance(target_mode)

        self._client = client
        self._connected_account_type = AccountType.PRACTICE if target_mode == "PRACTICE" else AccountType.REAL

    def current_account_type(self) -> AccountType:
        if self._connected_account_type is None:
            raise BrokerConnectionError("IQOptionGateway.connect() ainda não foi chamado.")
        return self._connected_account_type

    def get_balance(self) -> float:
        self._require_connected()
        # VERIFICAR: get_balance() -> float, saldo da conta ATIVA (a que foi
        # selecionada pelo último change_balance()).
        return float(self._client.get_balance())

    def place_order(self, request: OrderRequest) -> str:
        self._require_connected()

        # Trava 3 de 3 (seção 7): compara a conta da SESSÃO ATIVA com a
        # conta pedida pela ordem, no momento exato do envio. Não confia que
        # ExecutionConfig (trava 1) ou ExecutionGuard (trava 2) já
        # impediram isso — verificação redundante e independente das outras
        # duas, propositalmente.
        if self.current_account_type() != request.account_type:
            raise BrokerRejectionError(
                f"Conta da sessão ativa ({self.current_account_type().value}) diverge da "
                f"conta pedida pela ordem ({request.account_type.value}); ordem recusada "
                "antes de qualquer chamada de compra."
            )

        broker_direction = request.direction.to_broker_string()

        if request.instrument is InstrumentType.DIGITAL:
            # VERIFICAR: buy_digital_spot(active, amount, action, duration) -> (bool, order_id)
            # Envolvida em _call_with_timeout: este método especificamente
            # pode travar sem retornar (ver docstring de _call_with_timeout).
            ok, order_id = self._call_with_timeout(
                self._place_order_timeout_s,
                self._client.buy_digital_spot, request.symbol, request.stake, broker_direction, request.expiry_minutes
            )
        else:
            # VERIFICAR: buy(amount, active, action, expirations) -> (bool, order_id)
            ok, order_id = self._call_with_timeout(
                self._place_order_timeout_s,
                self._client.buy, request.stake, request.symbol, broker_direction, request.expiry_minutes
            )

        if not ok or order_id is None:
            raise BrokerRejectionError(
                f"IQ Option recusou a ordem (retorno bruto: ok={ok!r}, order_id={order_id!r})."
            )

        order_id_str = str(order_id)
        self._order_instruments[order_id_str] = request.instrument
        return order_id_str

    def await_result(
        self,
        broker_order_id: str,
        poll_interval_s: float,
        poll_timeout_s: float,
    ) -> ExecutionResult:
        self._require_connected()
        # Digital e binária são resolvidas por métodos DIFERENTES na lib —
        # ver o comentário em __init__ sobre _order_instruments. Default
        # BINARY só é alcançado se place_order() nunca populou o dict (não
        # deveria acontecer no fluxo normal do LiveExecutor).
        instrument = self._order_instruments.get(broker_order_id, InstrumentType.BINARY)
        deadline = time.monotonic() + poll_timeout_s

        while time.monotonic() < deadline:
            try:
                if instrument is InstrumentType.DIGITAL:
                    result = self._poll_digital_result(broker_order_id)
                else:
                    result = self._poll_binary_result(broker_order_id)
            except BrokerConnectionError:
                # a chamada de checagem em si travou e estourou seu próprio
                # timeout interno (_call_with_timeout) — trata como "ainda
                # não resolvido" e tenta de novo até poll_timeout_s.
                time.sleep(poll_interval_s)
                continue
            except Exception:
                # Algumas forks levantam enquanto o resultado ainda está
                # pendente, em vez de devolver um status "pendente" — trata
                # como "ainda não resolvido" e tenta de novo até o timeout.
                time.sleep(poll_interval_s)
                continue

            if result is not None:
                return result
            time.sleep(poll_interval_s)

        return ExecutionResult(
            status=ExecutionStatus.ERROR,
            error=f"Timeout aguardando resolução de {broker_order_id!r} após {poll_timeout_s}s.",
        )

    def _poll_binary_result(self, broker_order_id: str) -> Optional[ExecutionResult]:
        # VERIFICAR: check_win_v4(order_id) -> (status: str, profit: float),
        # onde status costuma ser "win" / "loose" / "equal". Algumas forks só
        # expõem check_win_v3 (sem estado de empate separado) — se for o
        # caso da fork instalada, um empate pode chegar mascarado como
        # profit==0 dentro de "win"; ajuste a leitura abaixo antes de
        # confiar nisto em conta real.
        status, profit = self._client.check_win_v4(broker_order_id)
        if status is None:
            return None

        status_text = str(status).lower()
        if status_text in ("win", "won"):
            return ExecutionResult(status=ExecutionStatus.WON, profit=float(profit), raw={"status": status, "profit": profit})
        if status_text in ("loose", "lose", "lost"):
            return ExecutionResult(status=ExecutionStatus.LOST, profit=float(profit), raw={"status": status, "profit": profit})
        if status_text in ("equal", "tie", "draw"):
            return ExecutionResult(status=ExecutionStatus.TIE, profit=0.0, raw={"status": status, "profit": profit})
        return None

    def _poll_digital_result(self, broker_order_id: str) -> Optional[ExecutionResult]:
        # VERIFICAR: check_win_digital_v2(order_id) -> (closed: bool, profit).
        # Ao contrário do binário, NÃO devolve um status "win"/"loose"/"equal"
        # explícito — só um profit líquido (stake já excluído, lido do código-
        # fonte do fork: close_profit - invest, ou pnl_realized). WON/LOST/TIE
        # são inferidos aqui pelo SINAL desse profit. Envolvida em
        # _call_with_timeout: tem o mesmo busy-wait sem timeout que
        # buy_digital_spot (achado real, ver docstring de _call_with_timeout).
        closed, profit = self._call_with_timeout(
            self._check_win_call_timeout_s, self._client.check_win_digital_v2, int(broker_order_id)
        )
        if not closed or profit is None:
            return None

        profit = float(profit)
        if profit > 0:
            status = ExecutionStatus.WON
        elif profit < 0:
            status = ExecutionStatus.LOST
        else:
            status = ExecutionStatus.TIE
        return ExecutionResult(status=status, profit=profit, raw={"closed": closed, "profit": profit})

    def _require_connected(self) -> None:
        if self._client is None:
            raise BrokerConnectionError("IQOptionGateway.connect() precisa ser chamado antes desta operação.")
