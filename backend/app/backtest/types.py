"""
Tipos do Backtest Engine (Sprint 6).

Determinístico, causal, auditável, independente da IQ Option. O único ponto de
contato com o resto do sistema é o `Signal` do Strategy Engine, consumido por
duck-typing (ver protocolos abaixo) para não acoplar o backtest ao pacote de
estratégias.

Seção 11 da spec: NÃO criar uma segunda enumeração de direção incompatível.
Por isso tentamos importar o SignalDirection real do projeto e só caímos num
fallback de MESMOS valores (CALL/PUT) se ele não estiver disponível.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Protocol, runtime_checkable

# --- Direção: reutilizar a do Strategy Engine (seção 11) -------------------
try:
    # Caminho real do Strategy Engine (Sprint 5): app/strategies/types.py.
    # Esse enum também tem um valor NONE, mas normalize_direction() abaixo só
    # aceita CALL/PUT — um Signal com direção NONE nunca é construído pelo
    # Strategy Engine real (StrategyEvaluation.signal é None nesse caso), então
    # nunca chega até aqui.
    from app.strategies.types import SignalDirection  # type: ignore
except Exception:  # fallback com os MESMOS valores, nunca incompatível
    class SignalDirection(str, Enum):
        CALL = "CALL"
        PUT = "PUT"


def normalize_direction(direction: Any) -> "SignalDirection":
    """Aceita o SignalDirection real ou a string CALL/PUT."""
    value = getattr(direction, "value", direction)
    value = str(value).upper()
    if value not in ("CALL", "PUT"):
        raise ValueError(f"Direção não operável: {value!r}")
    return SignalDirection(value)


# --- Resultado do trade (seção 10) -----------------------------------------
class TradeOutcome(str, Enum):
    """Empate é estado explícito. Nunca reduzir a True/False."""
    WIN = "WIN"
    LOSS = "LOSS"
    DRAW = "DRAW"


# --- Regime de mercado (seção 43) ------------------------------------------
class MarketRegime(str, Enum):
    TRENDING_BULLISH = "TRENDING_BULLISH"
    TRENDING_BEARISH = "TRENDING_BEARISH"
    RANGING = "RANGING"
    TRANSITION = "TRANSITION"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    UNKNOWN = "UNKNOWN"


# --- Motivos de não-execução (seções 22, 23, 49) ---------------------------
class SkipReason(str, Enum):
    NO_SIGNAL = "NO_SIGNAL"
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"   # seção 22
    UNRESOLVED = "UNRESOLVED"                        # seção 23 (sem candle futuro suficiente)
    DATA_GAP = "DATA_GAP"                            # seção 49
    POSITION_OPEN = "POSITION_OPEN"                  # modelo sequencial (ver engine)


class BacktestDataInvalid(Exception):
    """
    Seção 50: dados inconsistentes (fora de ordem, duplicados, OHLC inválido,
    timezone misturado) fazem o backtest FALHAR explicitamente. Nunca deduplicar
    ou consertar em silêncio.
    """


# --- Candle (duck-typing) --------------------------------------------------
@runtime_checkable
class Candle(Protocol):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class SimpleCandle:
    """Implementação concreta leve — usada em testes e como fallback."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


# --- Signal (duck-typing) --------------------------------------------------
@runtime_checkable
class SignalLike(Protocol):
    direction: Any  # algo cujo .value seja CALL/PUT


# --- TradeRecord (seção 9) -------------------------------------------------
@dataclass
class TradeRecord:
    id: str
    strategy: str
    symbol: str
    timeframe: str

    signal_timestamp: datetime
    entry_timestamp: datetime
    expiry_timestamp: datetime

    direction: SignalDirection

    entry_price: float
    exit_price: float

    stake: float
    payout: float

    outcome: TradeOutcome

    profit_loss: float

    balance_before: float
    balance_after: float

    signal_confidence: Optional[float] = None
    signal_strength: Optional[float] = None
    regime: MarketRegime = MarketRegime.UNKNOWN

    conditions: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkippedSignal:
    """Sinal que existiu mas não virou trade. Auditável (seções 22, 23, 49)."""
    signal_timestamp: datetime
    direction: Optional[SignalDirection]
    reason: SkipReason
    detail: str = ""


# --- Resultado do backtest (seção 31) --------------------------------------
@dataclass
class BacktestResult:
    run_id: str
    config: Any                      # BacktestConfig
    trades: list[TradeRecord]
    skipped: list[SkippedSignal]
    metrics: dict[str, Any]
    equity_curve: list[tuple[datetime, float]]
    drawdown: dict[str, Any]
