"""
Persistência de resultados de backtest.

Protocolo desacoplado + implementação em memória para dev/teste. Em produção,
implemente sobre o Postgres do projeto. NÃO reutilizar a futura tabela de
execução real (Sprint 7): backtest e execução têm campos e semântica distintos.
"""

from __future__ import annotations

from typing import Optional, Protocol

from .types import BacktestResult


class BacktestResultRepository(Protocol):
    def save(self, result: BacktestResult) -> None: ...
    def get(self, run_id: str) -> Optional[BacktestResult]: ...
    def list_all(self) -> list[BacktestResult]: ...


class InMemoryBacktestResultRepository:
    def __init__(self) -> None:
        self._store: dict[str, BacktestResult] = {}

    def save(self, result: BacktestResult) -> None:
        self._store[result.run_id] = result

    def get(self, run_id: str) -> Optional[BacktestResult]:
        return self._store.get(run_id)

    def list_all(self) -> list[BacktestResult]:
        return list(self._store.values())
