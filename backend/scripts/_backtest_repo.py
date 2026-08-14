"""Compartilhado por backtest_live_pair.py e screen_pairs.py."""

from __future__ import annotations

from datetime import datetime

from app.data.types import Candle


class InMemoryCandleRepository:
    """Satisfaz o Protocol `CandleRepository` do Backtest Engine com uma
    lista de candles já buscada uma vez — sem banco, sem repetir a chamada
    de rede a cada avaliação (o engine chama get_candles() uma única vez no
    início do run, não por candle)."""

    def __init__(self, candles: list[Candle]) -> None:
        self._candles = candles

    def get_candles(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> list[Candle]:
        return [c for c in self._candles if start <= c.timestamp <= end]
