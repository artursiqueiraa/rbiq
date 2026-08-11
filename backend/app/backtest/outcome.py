"""
Resolução de resultado e P&L (seções 17, 18, 19, 20).

Regras de direção:
  CALL: exit>entry→WIN | exit<entry→LOSS | exit==entry→DRAW
  PUT : exit<entry→WIN | exit>entry→LOSS | exit==entry→DRAW

P&L:
  WIN  → +stake*payout   (NÃO inclui o stake de volta — seção 20)
  LOSS → -stake
  DRAW → 0
"""

from __future__ import annotations

from .types import SignalDirection, TradeOutcome


def resolve_outcome(direction: SignalDirection, entry_price: float, exit_price: float) -> TradeOutcome:
    if entry_price == exit_price:
        return TradeOutcome.DRAW
    higher = exit_price > entry_price
    if direction is SignalDirection.CALL:
        return TradeOutcome.WIN if higher else TradeOutcome.LOSS
    else:  # PUT
        return TradeOutcome.WIN if not higher else TradeOutcome.LOSS


def compute_pl(outcome: TradeOutcome, stake: float, payout: float) -> float:
    if outcome is TradeOutcome.WIN:
        return stake * payout      # seção 19/20: só o lucro, sem o stake de volta
    if outcome is TradeOutcome.LOSS:
        return -stake
    return 0.0                     # DRAW
