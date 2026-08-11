"""
Backtest Engine (Sprint 6) — motor de backtest histórico determinístico,
causal e auditável para o IQO Strategy Lab.

Independente da IQ Option, de credenciais e de conta real. Consome os `Signal`
do Strategy Engine e simula o passado respeitando  dados <= T.

Uso típico:
    runner = BacktestRunner(candle_repo, strategy_service)
    result = runner.run(config)
    print(summary_text(result))
"""

from .adapters import CandleRepositoryAdapter, StrategyEvaluatorAdapter
from .config import BacktestConfig, StakeMode
from .engine import BacktestEngine, EngineOutput, StrategyService
from .equity import compute_drawdown
from .metrics import compute_metrics
from .outcome import compute_pl, resolve_outcome
from .portfolio import Portfolio
from .reports import summary_text, to_dict
from .repository import BacktestResultRepository, InMemoryBacktestResultRepository
from .runner import BacktestRunner, CandleRepository
from .simulator import ResolvedTrade, TradeSimulator
from .types import (
    BacktestDataInvalid,
    BacktestResult,
    Candle,
    MarketRegime,
    SignalDirection,
    SimpleCandle,
    SkippedSignal,
    SkipReason,
    TradeOutcome,
    TradeRecord,
    normalize_direction,
)
from .validation import expected_interval, validate_candles

__all__ = [
    "CandleRepositoryAdapter", "StrategyEvaluatorAdapter",
    "BacktestConfig", "StakeMode",
    "BacktestEngine", "EngineOutput", "StrategyService",
    "BacktestRunner", "CandleRepository",
    "TradeSimulator", "ResolvedTrade",
    "Portfolio",
    "compute_metrics", "compute_drawdown",
    "resolve_outcome", "compute_pl",
    "validate_candles", "expected_interval",
    "summary_text", "to_dict",
    "BacktestResultRepository", "InMemoryBacktestResultRepository",
    "BacktestResult", "TradeRecord", "TradeOutcome", "SkippedSignal", "SkipReason",
    "MarketRegime", "SignalDirection", "Candle", "SimpleCandle",
    "BacktestDataInvalid", "normalize_direction",
]
