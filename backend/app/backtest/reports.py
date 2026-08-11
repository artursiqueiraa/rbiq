"""
Relatórios do backtest.

Formata o BacktestResult em texto legível (resumo) e em dict serializável.
Não decide nada — só apresenta o que o engine/metrics produziram.
"""

from __future__ import annotations

from typing import Any

from .types import BacktestResult, SkipReason


def _fmt_pct(value: Any) -> str:
    return "n/a" if value is None else f"{value * 100:.2f}%"


def summary_text(result: BacktestResult) -> str:
    m = result.metrics
    dd = result.drawdown
    skip_counts: dict[str, int] = {}
    for s in result.skipped:
        skip_counts[s.reason.value] = skip_counts.get(s.reason.value, 0) + 1

    lines = [
        f"Backtest {result.run_id}",
        f"  estratégia   : {result.config.strategy}",
        f"  símbolo/TF   : {result.config.symbol} {result.config.timeframe}",
        f"  período      : {result.config.start} → {result.config.end}",
        f"  payout/stake : {result.config.payout} / {result.config.stake}  "
        f"(expiry={result.config.expiry_candles} candles)",
        "",
        f"  trades       : {m['total_trades']}  "
        f"(W {m['wins']} / L {m['losses']} / D {m['draws']})",
        f"  win_rate     : {_fmt_pct(m['win_rate'])}  (draws fora do denominador)",
        f"  P&L          : {m['profit_loss']:.2f}   ROI: {_fmt_pct(m['roi'])}",
        f"  profit_factor: {m['profit_factor'] if m['profit_factor'] is not None else 'n/a (sem perdas)'}",
        f"  expectancy   : {m['expectancy']:.4f}" if m['expectancy'] is not None else "  expectancy   : n/a",
        f"  avg win/loss : {m['average_win']:.2f} / {m['average_loss']:.2f}",
        f"  streaks      : +{m['longest_winning_streak']} / -{m['longest_losing_streak']} "
        f"(atual {m['current_streak']:+d})",
        f"  max drawdown : {dd['maximum_drawdown']:.2f} ({_fmt_pct(dd['maximum_drawdown_pct'])})",
        "",
        f"  não executados: {sum(skip_counts.values())}  {skip_counts or ''}",
    ]
    return "\n".join(lines)


def to_dict(result: BacktestResult) -> dict[str, Any]:
    return {
        "run_id": result.run_id,
        "config": {
            "symbol": result.config.symbol,
            "timeframe": result.config.timeframe,
            "strategy": result.config.strategy,
            "payout": result.config.payout,
            "stake": result.config.stake,
            "expiry_candles": result.config.expiry_candles,
            "initial_balance": result.config.initial_balance,
        },
        "metrics": result.metrics,
        "drawdown": result.drawdown,
        "trades": len(result.trades),
        "skipped": [
            {"timestamp": s.signal_timestamp.isoformat(), "reason": s.reason.value, "detail": s.detail}
            for s in result.skipped
        ],
        "equity_curve": [(ts.isoformat(), bal) for ts, bal in result.equity_curve],
    }
