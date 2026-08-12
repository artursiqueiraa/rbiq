"""
Tipos do Live Execution Engine (Sprint 7).

Broker-agnóstico, seguro por padrão (conta demo), auditável. O único ponto de
contato com o Strategy Engine é consumir um objeto parecido com `Signal` por
duck-typing (seção 17) — este módulo nunca importa `app.strategies`.

`OrderDirection` espelha `SignalDirection` do Strategy Engine (mesmos
valores CALL/PUT) sem importar o pacote de estratégias, pela mesma razão que
o Backtest Engine (Sprint 6) mantém seu próprio `SignalDirection`: os dois
consumidores do `Signal` (backtest e execução) não devem depender um do
outro, nem do pacote de estratégias além do necessário.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Protocol, runtime_checkable


class AccountType(str, Enum):
    """Seção 7. PRACTICE (demo) é o default em todo lugar que account_type
    aparece nesta Sprint — promover para REAL é sempre um ato explícito."""
    PRACTICE = "PRACTICE"
    REAL = "REAL"


class OrderDirection(str, Enum):
    CALL = "CALL"
    PUT = "PUT"

    def to_broker_string(self) -> str:
        """Seção 15: mapeamento fixo para o vocabulário que a lib espera."""
        return "call" if self is OrderDirection.CALL else "put"


class InstrumentType(str, Enum):
    """Seção 16. Define qual método da lib o IQOptionGateway usa — o resto do
    pipeline (guard, executor) não sabe nem precisa saber a diferença."""
    BINARY = "BINARY"
    DIGITAL = "DIGITAL"


class ExecutionStatus(str, Enum):
    """Seção 14. TIE é estado explícito (equivalente ao DRAW do backtest) —
    nunca reduzido a True/False."""
    PENDING = "PENDING"
    PLACED = "PLACED"
    WON = "WON"
    LOST = "LOST"
    TIE = "TIE"
    REJECTED = "REJECTED"
    ERROR = "ERROR"


def normalize_order_direction(direction: Any) -> OrderDirection:
    """Aceita OrderDirection, SignalDirection (duck-typed via .value) ou a
    string CALL/PUT diretamente."""
    value = getattr(direction, "value", direction)
    value = str(value).upper()
    if value not in ("CALL", "PUT"):
        raise ValueError(f"Direção não operável: {value!r}")
    return OrderDirection(value)


@runtime_checkable
class SignalLike(Protocol):
    """Seção 17: o único contrato que o Live Execution Engine exige de um
    Signal. `direction` é obrigatório (precisa existir e ter um `.value` ou
    ser diretamente CALL/PUT); os demais atributos são lidos via `getattr`
    com default em `executor.py` — nunca importamos `app.strategies.types`
    aqui para checar isso estruturalmente."""
    direction: Any


def compute_idempotency_key(symbol: str, signal_timestamp: Optional[datetime], direction: OrderDirection) -> str:
    """Seção 27: a MESMA combinação (symbol, signal_timestamp, direção) nunca
    gera duas ordens. `signal_timestamp` ausente usa um marcador fixo em vez
    de `datetime.now()` — um Signal sem timestamp é incomum, mas ainda assim
    precisa de uma chave determinística (duas chamadas com o mesmo Signal sem
    timestamp devem colidir, não duas chamadas aleatórias)."""
    ts = signal_timestamp.isoformat() if signal_timestamp else "no-timestamp"
    raw = f"{symbol}|{ts}|{direction.value}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class OrderRequest:
    """Seção 13. Imutável: uma vez montada e aprovada pela guarda, é
    exatamente o que vai à corretora — nada a mais é decidido depois disso."""

    symbol: str
    direction: OrderDirection
    stake: float
    expiry_minutes: int
    instrument: InstrumentType
    account_type: AccountType
    signal_timestamp: Optional[datetime] = None
    signal_confidence: Optional[float] = None
    signal_strength: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def idempotency_key(self) -> str:
        return compute_idempotency_key(self.symbol, self.signal_timestamp, self.direction)


@dataclass(frozen=True)
class ExecutionResult:
    """O que um `BrokerGateway.await_result` devolve — a resolução de UM
    trade já enviado, antes de virar um `ExecutionRecord` persistido.

    Seção 23, respeitada deliberadamente: `raw` guarda o payload bruto do
    broker (incluindo o profit como ELE o devolveu, em QUALQUER convenção que
    use). Não existe aqui nenhuma tentativa de normalizar isso para a
    convenção do backtest (`profit = stake*payout`) — essa reconciliação é
    trabalho de uma futura camada de métricas, não deste tipo.
    """

    status: ExecutionStatus  # WON | LOST | TIE | ERROR
    profit: Optional[float] = None   # o valor que o broker relatou, sem normalização
    payout: Optional[float] = None
    error: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionRecord:
    """Seção 24. Todo `LiveExecutor.execute()` produz exatamente um destes —
    inclusive quando a ordem é rejeitada pela guarda ou falha por erro de
    rede/corretora. `execute()` nunca levanta; isto é a prova disso."""

    id: str
    request: Optional[OrderRequest]
    status: ExecutionStatus
    profit: Optional[float]
    broker_order_id: Optional[str]
    balance_before: Optional[float]
    balance_after: Optional[float]
    payout_at_entry: Optional[float]
    placed_at: Optional[datetime]
    resolved_at: Optional[datetime]
    reject_reason: Optional[str] = None
    error: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def idempotency_key(self) -> Optional[str]:
        # None só no caso extremo em que nem o OrderRequest pôde ser
        # construído (sinal malformado) — o `LiveExecutor` nunca deixa isso
        # virar exceção (ver executor.py), mas também não finge que existe
        # uma ordem que nunca chegou a ser modelada.
        return self.request.idempotency_key if self.request is not None else None
