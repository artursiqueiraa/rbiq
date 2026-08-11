"""
Métricas do backtest (seções 35 a 47).

Definições explícitas e documentadas onde a spec exige:
  - win_rate = wins / (wins + losses)   (DRAW fora do denominador — seção 36).
    Se não há trades decisivos, win_rate = None (indefinido).
  - profit_factor = gross_profit / abs(gross_loss). Se gross_loss == 0 → None
    (nunca infinito silencioso — seção 37).
  - expectancy = total_profit_loss / total_trades. Como neste modelo todo trade
    executado está resolvido, "por trade" e "por trade resolvido" coincidem;
    documentado (seção 38).
  - DRAW é neutro em streaks: não estende nem soma como win/loss; reseta a
    contagem corrente (seção 40, documentado).
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from .types import MarketRegime, SignalDirection, TradeOutcome, TradeRecord


def _win_rate(wins: int, losses: int) -> Optional[float]:
    decisive = wins + losses
    return (wins / decisive) if decisive > 0 else None


def _bucket(trades: Sequence[TradeRecord]) -> dict[str, Any]:
    wins = sum(1 for t in trades if t.outcome is TradeOutcome.WIN)
    losses = sum(1 for t in trades if t.outcome is TradeOutcome.LOSS)
    draws = sum(1 for t in trades if t.outcome is TradeOutcome.DRAW)
    pl = sum(t.profit_loss for t in trades)
    return {
        "trades": len(trades),
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_rate": _win_rate(wins, losses),
        "profit_loss": pl,
    }


def compute_metrics(trades: Sequence[TradeRecord], initial_balance: float) -> dict[str, Any]:
    total = len(trades)
    wins = sum(1 for t in trades if t.outcome is TradeOutcome.WIN)
    losses = sum(1 for t in trades if t.outcome is TradeOutcome.LOSS)
    draws = sum(1 for t in trades if t.outcome is TradeOutcome.DRAW)

    gross_profit = sum(t.profit_loss for t in trades if t.profit_loss > 0)
    gross_loss = sum(t.profit_loss for t in trades if t.profit_loss < 0)
    total_pl = sum(t.profit_loss for t in trades)

    # profit factor (seção 37)
    profit_factor: Optional[float]
    profit_factor = (gross_profit / abs(gross_loss)) if gross_loss != 0 else None

    # médias (seção 39)
    win_pls = [t.profit_loss for t in trades if t.outcome is TradeOutcome.WIN]
    loss_pls = [t.profit_loss for t in trades if t.outcome is TradeOutcome.LOSS]
    average_win = (sum(win_pls) / len(win_pls)) if win_pls else 0.0
    average_loss = (sum(loss_pls) / len(loss_pls)) if loss_pls else 0.0

    metrics: dict[str, Any] = {
        # básicas (seção 35)
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_rate": _win_rate(wins, losses),                     # seção 36
        "profit_loss": total_pl,
        "roi": (total_pl / initial_balance) if initial_balance else None,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": profit_factor,                          # seção 37
        "expectancy": (total_pl / total) if total else None,     # seção 38
        "average_win": average_win,                              # seção 39
        "average_loss": average_loss,
        **_streaks(trades),                                      # seção 40
        "by_direction": _by_direction(trades),                  # seções 42, 46
        "by_regime": _by_regime(trades),                        # seção 43
        "by_hour": _by_hour(trades),                            # seção 44 (só análise)
        "by_weekday": _by_weekday(trades),                     # seção 45 (só análise)
        "by_expiry": _by_expiry(trades),                       # seção 47
    }
    return metrics


def _streaks(trades: Sequence[TradeRecord]) -> dict[str, Any]:
    longest_win = longest_loss = 0
    cur = 0  # positivo = wins seguidos; negativo = losses seguidos
    for t in trades:
        if t.outcome is TradeOutcome.WIN:
            cur = cur + 1 if cur > 0 else 1
            longest_win = max(longest_win, cur)
        elif t.outcome is TradeOutcome.LOSS:
            cur = cur - 1 if cur < 0 else -1
            longest_loss = max(longest_loss, -cur)
        else:  # DRAW é neutro: reseta
            cur = 0
    return {
        "longest_winning_streak": longest_win,
        "longest_losing_streak": longest_loss,
        "current_streak": cur,
    }


def _by_direction(trades: Sequence[TradeRecord]) -> dict[str, Any]:
    return {
        "CALL": _bucket([t for t in trades if t.direction is SignalDirection.CALL]),
        "PUT": _bucket([t for t in trades if t.direction is SignalDirection.PUT]),
    }


def _by_regime(trades: Sequence[TradeRecord]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for regime in MarketRegime:
        subset = [t for t in trades if t.regime is regime]
        if subset:
            out[regime.value] = _bucket(subset)
    return out


def _by_hour(trades: Sequence[TradeRecord]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for h in range(24):
        subset = [t for t in trades if t.entry_timestamp.hour == h]
        if subset:
            out[f"{h:02d}"] = _bucket(subset)
    return out


def _by_weekday(trades: Sequence[TradeRecord]) -> dict[str, Any]:
    names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    out: dict[str, Any] = {}
    for idx, name in enumerate(names):
        subset = [t for t in trades if t.entry_timestamp.weekday() == idx]
        if subset:
            out[name] = _bucket(subset)
    return out


def _by_expiry(trades: Sequence[TradeRecord]) -> dict[str, Any]:
    # expiry em candles derivado do metadata, se presente; caso contrário agrupa tudo.
    out: dict[str, Any] = {}
    for t in trades:
        key = str(t.metadata.get("expiry_candles", "n/a"))
        out.setdefault(key, []).append(t)
    return {k: _bucket(v) for k, v in out.items()}
