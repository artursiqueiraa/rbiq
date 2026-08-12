"""
PaperBroker — corretora de papel (Sprint 7, passo 4).

Default seguro: nenhuma chamada de rede, nenhuma ordem real, nenhuma
credencial. Resolve trades com um resultado probabilístico semeável — existe
para testar o PLUMBING do Live Execution Engine (guard -> executor ->
repository) de ponta a ponta, e nada além disso.

Este broker NÃO é um simulador de mercado. Para medir performance real de
estratégia, causal e determinística, o instrumento correto é o Backtest
Engine (Sprint 6) — `PaperBroker` não conhece candles, indicadores, nem
regime de mercado.
"""

from __future__ import annotations

import random
import time
import uuid
from typing import Optional

from .broker import BrokerConnectionError, BrokerGateway, BrokerRejectionError
from .types import AccountType, ExecutionResult, ExecutionStatus, OrderRequest


class PaperBroker(BrokerGateway):
    def __init__(
        self,
        initial_balance: float = 10_000.0,
        win_probability: float = 0.5,
        tie_probability: float = 0.0,
        payout: float = 0.80,
        seed: Optional[int] = None,
        latency_s: float = 0.0,
    ) -> None:
        if not 0.0 <= win_probability <= 1.0:
            raise ValueError("win_probability deve estar entre 0 e 1.")
        if not 0.0 <= tie_probability <= 1.0:
            raise ValueError("tie_probability deve estar entre 0 e 1.")
        if win_probability + tie_probability > 1.0:
            raise ValueError("win_probability + tie_probability não pode passar de 1.")

        self._balance = initial_balance
        self._win_probability = win_probability
        self._tie_probability = tie_probability
        self._payout = payout
        self._rng = random.Random(seed)
        self._latency_s = latency_s
        self._orders: dict[str, OrderRequest] = {}
        self._connected = False

        # Ganchos de teste (seção 8: cenários de recusa/erro do broker). Nenhum
        # código de produção seta estes atributos — são para os testes
        # forçarem deliberadamente os caminhos REJECTED/ERROR do LiveExecutor.
        self.force_place_rejection: Optional[str] = None
        self.force_connection_error: bool = False

    def connect(self) -> None:
        if self.force_connection_error:
            raise BrokerConnectionError("PaperBroker: falha de conexão forçada (teste).")
        self._connected = True

    def current_account_type(self) -> AccountType:
        return AccountType.PRACTICE

    def get_balance(self) -> float:
        return self._balance

    def place_order(self, request: OrderRequest) -> str:
        if self.force_place_rejection is not None:
            raise BrokerRejectionError(self.force_place_rejection)
        if request.stake > self._balance:
            raise BrokerRejectionError("Saldo insuficiente na conta de papel.")
        if self._latency_s:
            time.sleep(self._latency_s)

        broker_order_id = f"paper-{uuid.uuid4()}"
        self._orders[broker_order_id] = request
        self._balance -= request.stake
        return broker_order_id

    def await_result(
        self,
        broker_order_id: str,
        poll_interval_s: float,
        poll_timeout_s: float,
    ) -> ExecutionResult:
        request = self._orders.get(broker_order_id)
        if request is None:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error=f"broker_order_id desconhecido: {broker_order_id!r}",
            )

        roll = self._rng.random()
        if roll < self._tie_probability:
            self._balance += request.stake  # empate: stake devolvido, profit zero
            return ExecutionResult(
                status=ExecutionStatus.TIE,
                profit=0.0,
                payout=self._payout,
                raw={"broker_order_id": broker_order_id, "outcome": "TIE"},
            )

        won = roll < self._tie_probability + self._win_probability
        if won:
            profit = request.stake * self._payout
            self._balance += request.stake + profit
            return ExecutionResult(
                status=ExecutionStatus.WON,
                profit=profit,
                payout=self._payout,
                raw={"broker_order_id": broker_order_id, "outcome": "WON"},
            )

        profit = -request.stake
        return ExecutionResult(
            status=ExecutionStatus.LOST,
            profit=profit,
            payout=self._payout,
            raw={"broker_order_id": broker_order_id, "outcome": "LOST"},
        )
