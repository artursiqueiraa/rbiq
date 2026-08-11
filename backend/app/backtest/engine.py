"""
Backtest Engine — o loop causal (seções 3, 14, 24, 25, 26, 27).

Regra fundamental (seção 3): para o candle no índice i (timestamp T), a
estratégia enxerga SOMENTE candles[0..i]. Candles futuros existem no simulador
apenas para calcular o RESULTADO de um trade já decidido — nunca chegam à
estratégia. Isso é o que garante ausência de vazamento.

Modelo desta Sprint: SEQUENCIAL. Um novo sinal só abre trade se não houver
trade em aberto. Mantém o bookkeeping de saldo inequívoco (balance_before na
entrada, balance_after na resolução). Concorrência de posições fica como
extensão futura — a arquitetura permite, mas não é feita aqui.

Fluxo por índice i (seção 25):
  1. resolver trade pendente que expira em i
  2. se não há trade aberto: avaliar estratégia sobre candles[0..i]
  3. se há sinal: validar (candle futuro existe e dentro do período; sem gap;
     saldo suficiente) e abrir trade com entrada em close(i), expiração i+N
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Protocol, Sequence

from .config import BacktestConfig
from .portfolio import Portfolio
from .simulator import TradeSimulator
from .types import (
    Candle,
    MarketRegime,
    SignalDirection,
    SkippedSignal,
    SkipReason,
    TradeRecord,
    normalize_direction,
)


class StrategyService(Protocol):
    """
    Fronteira com o Strategy Engine (seção 28). O engine passa a visão causal
    (candles até T, inclusive) e recebe um Signal ou None.

    Espera-se que o Signal (se houver) tenha, por duck-typing:
        .direction  (-> CALL/PUT)
        .confidence (opcional)
        .strength   (opcional)
        .regime     (opcional; -> MarketRegime)
        .conditions (opcional; dict)
        .metadata   (opcional; dict)
    """
    def evaluate(self, candles: Sequence[Candle], parameters: dict[str, Any]) -> Optional[Any]: ...


@dataclass
class _PendingTrade:
    entry_index: int
    expiry_index: int
    direction: SignalDirection
    signal: Any
    balance_before: float


@dataclass
class EngineOutput:
    trades: list[TradeRecord]
    skipped: list[SkippedSignal]
    equity_curve: list[tuple[datetime, float]]


class BacktestEngine:
    def __init__(self, config: BacktestConfig, simulator: TradeSimulator | None = None) -> None:
        self._cfg = config
        self._sim = simulator or TradeSimulator()

    def run(
        self,
        candles: Sequence[Candle],
        strategy: StrategyService,
        gap_indices: set[int],
    ) -> EngineOutput:
        cfg = self._cfg
        n = len(candles)
        N = cfg.expiry_candles

        portfolio = Portfolio(cfg.initial_balance, cfg.allow_negative_balance)
        trades: list[TradeRecord] = []
        skipped: list[SkippedSignal] = []
        equity: list[tuple[datetime, float]] = [(candles[0].timestamp, portfolio.balance)]

        pending: Optional[_PendingTrade] = None

        for i in range(n):
            candle = candles[i]

            # 1. resolver trade pendente que expira exatamente aqui
            if pending is not None and pending.expiry_index == i:
                trades.append(self._resolve(pending, candles, portfolio))
                equity.append((candle.timestamp, portfolio.balance))
                pending = None

            # 2. se há trade aberto, não avaliamos novo sinal (modelo sequencial)
            if pending is not None:
                continue

            # avaliar estratégia SOMENTE com candles até i (causalidade — seção 27)
            causal_view = candles[: i + 1]
            signal = strategy.evaluate(causal_view, cfg.strategy_parameters)
            if signal is None:
                continue

            direction = normalize_direction(signal.direction)
            expiry_index = i + N

            # 3a. candle futuro suficiente E dentro do período (seções 23, 24)
            if expiry_index >= n:
                skipped.append(SkippedSignal(candle.timestamp, direction,
                                             SkipReason.UNRESOLVED,
                                             f"expiry {expiry_index} além do período"))
                continue

            # 3b. o período de holding não pode atravessar um gap (seção 49)
            if self._crosses_gap(i, expiry_index, gap_indices):
                skipped.append(SkippedSignal(candle.timestamp, direction,
                                             SkipReason.DATA_GAP,
                                             f"gap entre {i} e {expiry_index}"))
                continue

            # 3c. saldo suficiente (seção 22)
            if not portfolio.can_open(cfg.stake):
                skipped.append(SkippedSignal(candle.timestamp, direction,
                                             SkipReason.INSUFFICIENT_BALANCE,
                                             f"saldo {portfolio.balance} < stake {cfg.stake}"))
                continue

            # abrir: entrada em close(i), expiração em i+N
            pending = _PendingTrade(
                entry_index=i,
                expiry_index=expiry_index,
                direction=direction,
                signal=signal,
                balance_before=portfolio.balance,
            )

        # sinal que ficou aberto no fim da série sem candle de expiração:
        # não executado (não conta como trade) — coerente com seção 23.
        if pending is not None:
            entry_candle = candles[pending.entry_index]
            skipped.append(SkippedSignal(entry_candle.timestamp, pending.direction,
                                         SkipReason.UNRESOLVED, "série terminou antes da expiração"))

        return EngineOutput(trades=trades, skipped=skipped, equity_curve=equity)

    # ------------------------------------------------------------------ helpers
    def _resolve(self, pending: _PendingTrade, candles: Sequence[Candle],
                 portfolio: Portfolio) -> TradeRecord:
        cfg = self._cfg
        entry_candle = candles[pending.entry_index]
        exit_candle = candles[pending.expiry_index]

        resolved = self._sim.resolve(
            entry_candle, exit_candle, pending.direction, cfg.stake, cfg.payout
        )
        balance_before = pending.balance_before
        portfolio.apply(resolved.profit_loss)
        balance_after = portfolio.balance

        sig = pending.signal
        return TradeRecord(
            id=str(uuid.uuid4()),
            strategy=cfg.strategy,
            symbol=cfg.symbol,
            timeframe=cfg.timeframe,
            signal_timestamp=entry_candle.timestamp,   # seção 12: signal_ts == entry_ts
            entry_timestamp=entry_candle.timestamp,
            expiry_timestamp=exit_candle.timestamp,
            direction=pending.direction,
            entry_price=resolved.entry_price,
            exit_price=resolved.exit_price,
            stake=cfg.stake,
            payout=cfg.payout,
            outcome=resolved.outcome,
            profit_loss=resolved.profit_loss,
            balance_before=balance_before,
            balance_after=balance_after,
            signal_confidence=getattr(sig, "confidence", None),
            signal_strength=getattr(sig, "strength", None),
            regime=self._extract_regime(sig),
            conditions=dict(getattr(sig, "conditions", {}) or {}),
            metadata=dict(getattr(sig, "metadata", {}) or {}),
        )

    @staticmethod
    def _crosses_gap(entry_index: int, expiry_index: int, gap_indices: set[int]) -> bool:
        # há gap se algum j em [entry_index, expiry_index-1] for fronteira de gap
        return any(j in gap_indices for j in range(entry_index, expiry_index))

    @staticmethod
    def _extract_regime(signal: Any) -> MarketRegime:
        raw = getattr(signal, "regime", None)
        if raw is None:
            raw = (getattr(signal, "conditions", {}) or {}).get("regime")
        if raw is None:
            return MarketRegime.UNKNOWN
        try:
            return MarketRegime(getattr(raw, "value", raw))
        except Exception:
            return MarketRegime.UNKNOWN
