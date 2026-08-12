"""
LiveExecutor — orquestra Signal -> guard -> broker -> ExecutionRecord
(Sprint 7, passo 7).

Contrato inegociável: `execute()` NUNCA levanta para o chamador. Toda falha
possível (sinal malformado, recusa da guarda, recusa do broker, erro de
rede/sessão, timeout de resolução) vira um `ExecutionRecord` com o status e
o motivo apropriados. Um loop de trading ao vivo não pode morrer porque uma
única iteração teve um problema.

`symbol` é passado explicitamente a `execute()`, e não lido de dentro do
`Signal` — o `Signal` do Strategy Engine é duck-typed por `.direction`
(seção 17), e o símbolo já é conhecido por quem está chamando (é o mesmo
símbolo usado para montar o `StrategyContext` que gerou o sinal).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from .broker import BrokerConnectionError, BrokerGateway, BrokerRejectionError
from .config import ExecutionConfig
from .guard import ExecutionGuard
from .repository import ExecutionRepository
from .types import (
    ExecutionRecord,
    ExecutionStatus,
    OrderRequest,
    compute_idempotency_key,
    normalize_order_direction,
)


class LiveExecutor:
    def __init__(
        self,
        broker: BrokerGateway,
        guard: ExecutionGuard,
        repository: ExecutionRepository,
        config: ExecutionConfig,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        id_factory: Callable[[], str] = lambda: str(uuid.uuid4()),
    ) -> None:
        self._broker = broker
        self._guard = guard
        self._repository = repository
        self._config = config
        self._clock = clock
        self._id_factory = id_factory

    def execute(self, signal: Any, symbol: str) -> ExecutionRecord:
        try:
            return self._execute(signal, symbol)
        except Exception as exc:  # nunca escapa (contrato central desta Sprint)
            return self._save(
                ExecutionRecord(
                    id=self._id_factory(),
                    request=None,
                    status=ExecutionStatus.ERROR,
                    profit=None,
                    broker_order_id=None,
                    balance_before=None,
                    balance_after=None,
                    payout_at_entry=None,
                    placed_at=None,
                    resolved_at=self._clock(),
                    error=f"Falha inesperada ao processar sinal: {exc}",
                )
            )

    # ------------------------------------------------------------- internals
    def _execute(self, signal: Any, symbol: str) -> ExecutionRecord:
        direction = normalize_order_direction(signal.direction)
        timestamp = getattr(signal, "timestamp", None)
        confidence = getattr(signal, "confidence", None)
        strength = getattr(signal, "strength", None)
        strength_value = getattr(strength, "value", strength)

        idempotency_key = compute_idempotency_key(symbol, timestamp, direction)
        existing = self._repository.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            # Mesmo Signal já processado (seção 27): devolve o registro
            # existente em vez de enviar uma segunda ordem.
            return existing

        request = OrderRequest(
            symbol=symbol,
            direction=direction,
            stake=self._config.fixed_stake,
            expiry_minutes=self._config.expiry_minutes,
            instrument=self._config.instrument,
            account_type=self._config.account_type,
            signal_timestamp=timestamp,
            signal_confidence=confidence,
            signal_strength=strength_value,
        )

        decision = self._guard.check(request)
        if not decision.allowed:
            return self._save(
                self._record(request, status=ExecutionStatus.REJECTED, reject_reason=decision.reason)
            )

        balance_before: Optional[float] = None
        try:
            self._broker.connect()
            balance_before = self._broker.get_balance()
        except Exception as exc:
            return self._save(
                self._record(request, status=ExecutionStatus.ERROR, error=str(exc), balance_before=balance_before)
            )

        try:
            broker_order_id = self._broker.place_order(request)
        except BrokerRejectionError as exc:
            return self._save(
                self._record(
                    request,
                    status=ExecutionStatus.REJECTED,
                    reject_reason=str(exc),
                    balance_before=balance_before,
                )
            )
        except (BrokerConnectionError, Exception) as exc:
            return self._save(
                self._record(request, status=ExecutionStatus.ERROR, error=str(exc), balance_before=balance_before)
            )

        placed_at = self._clock()
        self._guard.record_placed()

        try:
            result = self._broker.await_result(
                broker_order_id, self._config.poll_interval_s, self._config.poll_timeout_s
            )
        except Exception as exc:
            # A ordem foi enviada mas nunca soubemos o resultado: conta como
            # aberta resolvida sem lucro/perda conhecido, para não travar a
            # guarda de ordens concorrentes indefinidamente.
            self._guard.record_resolved(0.0)
            return self._save(
                self._record(
                    request,
                    status=ExecutionStatus.ERROR,
                    error=str(exc),
                    broker_order_id=broker_order_id,
                    balance_before=balance_before,
                    placed_at=placed_at,
                )
            )

        resolved_at = self._clock()
        profit = result.profit if result.profit is not None else 0.0
        self._guard.record_resolved(profit)

        try:
            balance_after = self._broker.get_balance()
        except Exception:
            balance_after = None

        return self._save(
            ExecutionRecord(
                id=self._id_factory(),
                request=request,
                status=result.status,
                profit=result.profit,
                broker_order_id=broker_order_id,
                balance_before=balance_before,
                balance_after=balance_after,
                payout_at_entry=result.payout,
                placed_at=placed_at,
                resolved_at=resolved_at,
                error=result.error,
                raw=result.raw,
            )
        )

    def _record(
        self,
        request: OrderRequest,
        *,
        status: ExecutionStatus,
        reject_reason: Optional[str] = None,
        error: Optional[str] = None,
        broker_order_id: Optional[str] = None,
        balance_before: Optional[float] = None,
        placed_at: Optional[datetime] = None,
    ) -> ExecutionRecord:
        now = self._clock()
        return ExecutionRecord(
            id=self._id_factory(),
            request=request,
            status=status,
            profit=None,
            broker_order_id=broker_order_id,
            balance_before=balance_before,
            balance_after=balance_before,
            payout_at_entry=None,
            placed_at=placed_at,
            resolved_at=now,
            reject_reason=reject_reason,
            error=error,
        )

    def _save(self, record: ExecutionRecord) -> ExecutionRecord:
        self._repository.save(record)
        return record
