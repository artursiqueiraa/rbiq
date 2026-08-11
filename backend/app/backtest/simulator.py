"""
Simulador de trade unitário (seções 13, 16, 17, 18, 19).

Função pura e determinística: dado o candle de entrada e o de saída, produz o
resultado. Não conhece saldo, não conhece o loop — só a mecânica de um trade.

Convenção de preço (seção 13): a estratégia foi avaliada no FECHAMENTO de T,
então a entrada usa close(T). A saída usa close(T+N) (seção 16). Nunca open().
"""

from __future__ import annotations

from dataclasses import dataclass

from .outcome import compute_pl, resolve_outcome
from .types import Candle, SignalDirection, TradeOutcome


@dataclass(frozen=True)
class ResolvedTrade:
    entry_price: float
    exit_price: float
    outcome: TradeOutcome
    profit_loss: float


class TradeSimulator:
    def resolve(
        self,
        entry_candle: Candle,
        exit_candle: Candle,
        direction: SignalDirection,
        stake: float,
        payout: float,
    ) -> ResolvedTrade:
        entry_price = entry_candle.close    # close(T)
        exit_price = exit_candle.close      # close(T+N)
        outcome = resolve_outcome(direction, entry_price, exit_price)
        pl = compute_pl(outcome, stake, payout)
        return ResolvedTrade(entry_price, exit_price, outcome, pl)
