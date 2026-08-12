"""
Interface abstrata do broker (Sprint 7, passo 3).

Qualquer corretora (`PaperBroker`, `IQOptionGateway`, ou uma futura corretora
diferente) implementa este contrato. `LiveExecutor` e `ExecutionGuard`
conhecem apenas este tipo — nunca importam `paper.py`/`iqoption.py`
diretamente fora do ponto de composição (wiring de app).

`current_account_type()` existe especificamente para permitir a trava 3 de 3
(seção 7): antes de enviar qualquer ordem, o gateway concreto compara a
conta da SESSÃO ATIVA com `request.account_type` e recusa em caso de
divergência — checagem feita de novo, independente de `ExecutionConfig` e do
`ExecutionGuard`, porque nenhuma das três travas confia que as outras já
rodaram.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .types import AccountType, ExecutionResult, OrderRequest


class BrokerConnectionError(RuntimeError):
    """Falha de rede/sessão ao falar com o broker (não é uma recusa da ordem)."""


class BrokerRejectionError(RuntimeError):
    """O broker recusou a ordem explicitamente (saldo, ativo fechado, etc.)."""


class BrokerGateway(ABC):
    """Broker-agnóstico por design (seção 6). Nenhum método aqui menciona
    IQ Option, martingale, ou qualquer conceito específico de uma corretora."""

    @abstractmethod
    def connect(self) -> None:
        """Estabelece/renova a sessão. Implementações reais fazem qualquer
        import de biblioteca de terceiros DENTRO deste método, nunca no topo
        do módulo (seção 9 do escopo de iqoption.py)."""
        raise NotImplementedError

    @abstractmethod
    def current_account_type(self) -> AccountType:
        """A conta que a sessão ATIVA está usando agora — não a que foi
        configurada. Base da trava 3 de 3 contra operar REAL por engano."""
        raise NotImplementedError

    @abstractmethod
    def get_balance(self) -> float:
        raise NotImplementedError

    @abstractmethod
    def place_order(self, request: OrderRequest) -> str:
        """Envia a ordem e devolve o `broker_order_id`. Nunca decide o
        resultado final aqui — isso é responsabilidade de `await_result`.

        Deve levantar `BrokerRejectionError` para recusas explícitas do
        broker e `BrokerConnectionError` para falhas de rede/sessão — o
        `LiveExecutor` distingue os dois para popular `reject_reason` vs
        `error` no `ExecutionRecord` (seção 24), mas em NENHUM dos dois
        casos deixa a exceção escapar para o chamador."""
        raise NotImplementedError

    @abstractmethod
    def await_result(
        self,
        broker_order_id: str,
        poll_interval_s: float,
        poll_timeout_s: float,
    ) -> ExecutionResult:
        """Aguarda a resolução de uma ordem já enviada. DEVE respeitar
        `poll_timeout_s` e devolver um `ExecutionResult` com
        `status=ExecutionStatus.ERROR` em caso de timeout — nunca bloquear
        indefinidamente (seção 21)."""
        raise NotImplementedError
