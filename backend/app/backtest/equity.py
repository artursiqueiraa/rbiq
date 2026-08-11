"""
Equity curve e drawdown (seções 32, 33, 34).

drawdown_pct = (peak - current) / peak
Registra peak/trough/recovery quando possível.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Sequence


def compute_drawdown(equity_curve: Sequence[tuple[datetime, float]]) -> dict[str, Any]:
    if not equity_curve:
        return {
            "maximum_drawdown": 0.0, "maximum_drawdown_pct": 0.0,
            "peak_timestamp": None, "trough_timestamp": None, "recovery_timestamp": None,
        }

    peak_value = equity_curve[0][1]
    peak_ts = equity_curve[0][0]

    max_dd = 0.0
    max_dd_pct = 0.0
    dd_peak_ts: Optional[datetime] = None
    dd_trough_ts: Optional[datetime] = None
    recovery_ts: Optional[datetime] = None

    # timestamps auxiliares do drawdown máximo em andamento
    cur_peak_ts = peak_ts

    for ts, value in equity_curve:
        if value > peak_value:
            peak_value = value
            cur_peak_ts = ts
            # se estávamos num drawdown e recuperamos o topo anterior, marca recovery
            if dd_trough_ts is not None and recovery_ts is None:
                recovery_ts = ts
            continue

        drawdown = peak_value - value
        drawdown_pct = (drawdown / peak_value) if peak_value != 0 else 0.0
        if drawdown_pct > max_dd_pct:
            max_dd = drawdown
            max_dd_pct = drawdown_pct
            dd_peak_ts = cur_peak_ts
            dd_trough_ts = ts
            recovery_ts = None  # recovery do novo pior drawdown ainda não ocorreu

    return {
        "maximum_drawdown": max_dd,
        "maximum_drawdown_pct": max_dd_pct,
        "peak_timestamp": dd_peak_ts,
        "trough_timestamp": dd_trough_ts,
        "recovery_timestamp": recovery_ts,   # None se nunca recuperou (seção 41)
    }
