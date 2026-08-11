"""
Configuração do backtest (seções 5, 6, 7, 8, 21, 51).

Payout e stake são PARÂMETROS do cenário, nunca hardcoded espalhados pelo
código. Stake é fixo nesta Sprint (sem martingale/soros/progressão).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class StakeMode(str, Enum):
    """Seção 7. Nesta Sprint só FIXED_STAKE. Sem progressão (seção 8)."""
    FIXED_STAKE = "FIXED_STAKE"


@dataclass
class BacktestConfig:
    # --- instrumento / período (seção 5) ---
    symbol: str
    timeframe: str
    start: datetime
    end: datetime

    # --- estratégia ---
    strategy: str
    strategy_parameters: dict[str, Any] = field(default_factory=dict)

    # --- dinheiro ---
    initial_balance: float = 1000.0
    stake: float = 10.0
    stake_mode: StakeMode = StakeMode.FIXED_STAKE
    payout: float = 0.80              # exemplo; NÃO é um payout "real" (seção 5/6)

    # --- expiração (seções 15, 16) ---
    expiry_candles: int = 1

    # --- comportamento ---
    allow_negative_balance: bool = False   # seção 21
    gap_tolerance: float = 1.5             # múltiplo do intervalo esperado p/ marcar gap (seção 49)

    def __post_init__(self) -> None:
        # timezone-aware, sem mistura naive/aware (seção 51)
        for name, dt in (("start", self.start), ("end", self.end)):
            if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
                raise ValueError(f"{name} deve ser timezone-aware (seção 51). Prefira UTC.")
        if self.start >= self.end:
            raise ValueError("start deve ser anterior a end.")
        if self.payout <= 0:
            raise ValueError("payout deve ser > 0 (seção 6).")
        if self.stake <= 0:
            raise ValueError("stake deve ser > 0.")
        if self.initial_balance <= 0:
            raise ValueError("initial_balance deve ser > 0.")
        if self.expiry_candles < 1:
            raise ValueError("expiry_candles deve ser >= 1 (seção 14: nunca o próprio candle T).")
