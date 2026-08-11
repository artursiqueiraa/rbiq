"""
Controle de saldo (seções 21, 22).

Modelo de P&L líquido: o saldo é atualizado por profit_loss na RESOLUÇÃO do
trade (WIN=+stake*payout, LOSS=-stake, DRAW=0). Não separamos "stake retido"
porque a convenção da spec (seção 19) já é líquida.
"""

from __future__ import annotations


class Portfolio:
    def __init__(self, initial_balance: float, allow_negative: bool = False) -> None:
        self._initial = initial_balance
        self._balance = initial_balance
        self._allow_negative = allow_negative

    @property
    def balance(self) -> float:
        return self._balance

    @property
    def initial_balance(self) -> float:
        return self._initial

    def can_open(self, stake: float) -> bool:
        """Seção 22: se saldo < stake, não abrir. O backtest não inventa dinheiro."""
        return self._balance >= stake

    def apply(self, profit_loss: float) -> None:
        """Atualiza saldo na resolução (seção 21). Bloqueia negativo salvo se configurado."""
        new_balance = self._balance + profit_loss
        if new_balance < 0 and not self._allow_negative:
            # Não deveria acontecer se can_open() foi respeitado, mas protege a invariante.
            raise ValueError(
                f"Saldo ficaria negativo ({new_balance}) sem allow_negative_balance."
            )
        self._balance = new_balance
