"""
Persistência de `ExecutionRecord` (Sprint 7, passo 6).

Protocolo desacoplado + implementação em memória para dev/teste. Em
produção, implementar sobre o Postgres do projeto, numa tabela PRÓPRIA
(`execution_records`) — nunca reutilizar a tabela de resultados do Backtest
Engine (Sprint 6): os campos e a semântica são distintos (broker_order_id,
account_type, latência, profit bruto e não-normalizado do broker).

`get_by_idempotency_key` existe especificamente para a regra de idempotência
(seção 27): antes de enviar uma ordem, o `LiveExecutor` consulta por esta
chave — se já existir um registro, a ordem NÃO é reenviada.
"""

from __future__ import annotations

from typing import Optional, Protocol

from .types import ExecutionRecord


class ExecutionRepository(Protocol):
    def save(self, record: ExecutionRecord) -> None: ...
    def get(self, record_id: str) -> Optional[ExecutionRecord]: ...
    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[ExecutionRecord]: ...
    def list_all(self) -> list[ExecutionRecord]: ...


class InMemoryExecutionRepository:
    def __init__(self) -> None:
        self._by_id: dict[str, ExecutionRecord] = {}
        self._id_by_idempotency_key: dict[str, str] = {}

    def save(self, record: ExecutionRecord) -> None:
        self._by_id[record.id] = record
        if record.idempotency_key is not None:
            self._id_by_idempotency_key[record.idempotency_key] = record.id

    def get(self, record_id: str) -> Optional[ExecutionRecord]:
        return self._by_id.get(record_id)

    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[ExecutionRecord]:
        record_id = self._id_by_idempotency_key.get(idempotency_key)
        return self._by_id.get(record_id) if record_id is not None else None

    def list_all(self) -> list[ExecutionRecord]:
        return list(self._by_id.values())
