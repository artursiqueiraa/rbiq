"""
ExecutionGuard — a última linha de defesa antes de qualquer ordem sair
(Sprint 7, passo 5). `LiveExecutor` chama `check()` para TODA ordem, sem
exceção, mesmo em conta de papel — a guarda não sabe nem precisa saber que
está em modo de teste.

Contém a trava 2 de 3 contra conta REAL (seção 7/12): verificada de novo
aqui, em runtime, por request, independentemente de `ExecutionConfig`
já ter validado isso na construção. As duas travas não compartilham estado —
uma config adulterada em memória depois de construída ainda cairia aqui.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Callable, Optional

from .config import ExecutionConfig
from .types import AccountType, OrderRequest


@dataclass
class GuardState:
    """Estado mutável e observável da guarda. Passado explicitamente (em vez
    de escondido dentro do `ExecutionGuard`) para que testes possam inspecionar
    e para que, futuramente, seja persistido/recuperado entre reinícios do
    processo sem acoplar a guarda a um mecanismo de storage específico."""

    daily_pnl: float = 0.0
    daily_trades: int = 0
    open_orders: int = 0
    current_day: Optional[date] = None


@dataclass(frozen=True)
class GuardDecision:
    allowed: bool
    reason: Optional[str] = None


class ExecutionGuard:
    def __init__(
        self,
        config: ExecutionConfig,
        state: Optional[GuardState] = None,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._config = config
        self._state = state or GuardState()
        self._clock = clock

    @property
    def state(self) -> GuardState:
        return self._state

    def _roll_day_if_needed(self) -> None:
        today = self._clock().date()
        if self._state.current_day != today:
            self._state.current_day = today
            self._state.daily_pnl = 0.0
            self._state.daily_trades = 0
            # open_orders é estado ao vivo (ordens ainda não resolvidas),
            # não é uma contagem diária — não reseta na virada do dia.

    def check(self, request: OrderRequest) -> GuardDecision:
        """Chamado pelo `LiveExecutor` ANTES de tocar o broker. Retorna uma
        decisão em vez de levantar exceção — recusa é um resultado normal e
        esperado, não uma falha do sistema."""
        self._roll_day_if_needed()

        # kill switch: seção "escopo" — rejeita tudo, sem reinício de processo.
        # Checado em `self._config` diretamente (o mesmo objeto que o
        # operador liga/desliga em runtime), nunca em uma cópia.
        if self._config.kill_switch:
            return GuardDecision(False, "KILL_SWITCH_ATIVO")

        # Trava 2 de 3 contra conta REAL (independente da trava 1 em
        # ExecutionConfig.__post_init__ e da trava 3 em IQOptionGateway).
        if request.account_type is AccountType.REAL:
            if not (self._config.account_type is AccountType.REAL and self._config.allow_real):
                return GuardDecision(False, "CONTA_REAL_NAO_AUTORIZADA")

        # Sem progressão de stake, nunca (martingale/soros/compounding
        # proibidos por especificação): toda ordem tem que usar exatamente o
        # stake fixo configurado.
        if request.stake != self._config.fixed_stake:
            return GuardDecision(False, "STAKE_DIVERGENTE_DO_FIXO_CONFIGURADO")

        if self._config.max_daily_trades is not None and self._state.daily_trades >= self._config.max_daily_trades:
            return GuardDecision(False, "LIMITE_DIARIO_DE_TRADES_ATINGIDO")

        if self._config.max_daily_loss is not None and self._state.daily_pnl <= -abs(self._config.max_daily_loss):
            return GuardDecision(False, "LIMITE_DIARIO_DE_PERDA_ATINGIDO")

        if self._state.open_orders >= self._config.max_concurrent_orders:
            return GuardDecision(False, "LIMITE_DE_ORDENS_CONCORRENTES_ATINGIDO")

        return GuardDecision(True, None)

    def record_placed(self) -> None:
        """Chamado pelo executor assim que o broker aceita a ordem. Também
        rola o dia se necessário — sem isto, um `record_placed()` chamado
        antes do primeiro `check()` do dia ficaria com `current_day=None` e
        seria apagado pelo primeiro `check()` subsequente."""
        self._roll_day_if_needed()
        self._state.open_orders += 1
        self._state.daily_trades += 1

    def record_resolved(self, profit: float) -> None:
        """Chamado pelo executor quando a ordem é resolvida (WON/LOST/TIE/ERROR)."""
        self._roll_day_if_needed()
        self._state.open_orders = max(0, self._state.open_orders - 1)
        self._state.daily_pnl += profit
