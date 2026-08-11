"""
Qualidade de dados (seções 48, 49, 50, 51).

Antes do backtest: validar timezone, ordenação, duplicatas, OHLC e gaps.
Inconsistência → BacktestDataInvalid (falha explícita, sem conserto silencioso).
Gaps não invalidam o dataset, mas são marcados para o engine impedir operações
cujo período atravesse um gap.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Sequence

from .types import BacktestDataInvalid, Candle

# intervalos esperados por timeframe (segundos)
_TF_SECONDS = {
    "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
    "H1": 3600, "H4": 14400, "D1": 86400,
}


def expected_interval(timeframe: str) -> timedelta | None:
    secs = _TF_SECONDS.get(timeframe.upper())
    return timedelta(seconds=secs) if secs else None


def validate_candles(candles: Sequence[Candle], timeframe: str, gap_tolerance: float = 1.5) -> set[int]:
    """
    Valida a série e retorna o conjunto de índices `i` que têm um GAP entre
    candle[i] e candle[i+1] (fronteiras de gap). Levanta BacktestDataInvalid
    em qualquer inconsistência dura.
    """
    if not candles:
        raise BacktestDataInvalid("Nenhum candle para o período solicitado.")

    interval = expected_interval(timeframe)
    gap_indices: set[int] = set()
    prev = None

    for i, c in enumerate(candles):
        # timezone-aware, sem mistura (seção 51)
        ts = c.timestamp
        if ts.tzinfo is None or ts.tzinfo.utcoffset(ts) is None:
            raise BacktestDataInvalid(f"Candle {i} tem timestamp naive (seção 51).")

        # OHLC coerente (seção 48)
        if not (c.high >= c.low
                and c.high >= c.open and c.high >= c.close
                and c.low <= c.open and c.low <= c.close):
            raise BacktestDataInvalid(f"Candle {i} tem OHLC inconsistente: "
                                      f"O={c.open} H={c.high} L={c.low} C={c.close}")

        if prev is not None:
            # ordenação estrita + sem duplicatas (seção 50)
            if ts <= prev.timestamp:
                raise BacktestDataInvalid(
                    f"Candles fora de ordem ou duplicados em {i}: "
                    f"{prev.timestamp} -> {ts} (seção 50)."
                )
            # gap (seção 49): delta maior que tolerância do intervalo esperado
            if interval is not None:
                delta = ts - prev.timestamp
                if delta > interval * gap_tolerance:
                    gap_indices.add(i - 1)  # gap ENTRE i-1 e i

        prev = c

    return gap_indices
