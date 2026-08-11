"""
BacktestRunner (seções 28, 30, 31).

Orquestra: config → carregar candles (via CandleRepository) → validar qualidade
→ rodar engine → gerar métricas/equity/drawdown → BacktestResult.

Reutiliza serviços existentes por Protocol (seção 28), sem duplicar Market
Structure / Indicators / Strategy.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional, Protocol, Sequence

from .config import BacktestConfig
from .engine import BacktestEngine, StrategyService
from .equity import compute_drawdown
from .metrics import compute_metrics
from .simulator import TradeSimulator
from .types import BacktestResult, Candle
from .validation import validate_candles


class CandleRepository(Protocol):
    """Fronteira com o Data Engine. Deve devolver candles DENTRO de [start, end]."""
    def get_candles(self, symbol: str, timeframe: str, start, end) -> Sequence[Candle]: ...


class BacktestRunner:
    def __init__(
        self,
        candle_repository: CandleRepository,
        strategy_service: StrategyService,
        simulator: Optional[TradeSimulator] = None,
    ) -> None:
        self._candles = candle_repository
        self._strategy = strategy_service
        self._sim = simulator or TradeSimulator()

    def run(self, config: BacktestConfig) -> BacktestResult:
        # 1. carregar candles do período (seção 24: nada além de [start, end])
        candles = list(self._candles.get_candles(
            config.symbol, config.timeframe, config.start, config.end
        ))

        # 2. qualidade de dados (seções 48-51); pode levantar BacktestDataInvalid
        gap_indices = validate_candles(candles, config.timeframe, config.gap_tolerance)

        # 3. loop causal
        engine = BacktestEngine(config, self._sim)
        output = engine.run(candles, self._strategy, gap_indices)

        # anotar expiry nos trades para o bucket by_expiry (seção 47)
        for t in output.trades:
            t.metadata.setdefault("expiry_candles", config.expiry_candles)

        # 4. métricas + drawdown
        metrics = compute_metrics(output.trades, config.initial_balance)
        drawdown = compute_drawdown(output.equity_curve)

        return BacktestResult(
            run_id=str(uuid.uuid4()),
            config=config,
            trades=output.trades,
            skipped=output.skipped,
            metrics=metrics,
            equity_curve=output.equity_curve,
            drawdown=drawdown,
        )
