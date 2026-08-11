from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import ClassVar

from app.strategies.context import StrategyContext
from app.strategies.types import IndicatorRequest, Signal, SignalDirection, SignalStrength, StrategyEvaluation

DEFAULT_MIN_CONFIDENCE = 0.70


@dataclass(frozen=True)
class ConditionCheck:
    """One named, boolean, human-readable check. `name` is what ends up in
    Signal.conditions / StrategyEvaluation.triggered_conditions — it must be
    self-explanatory on its own (section 11: "por que o bot entrou aqui?")."""

    name: str
    passed: bool


def last_value(series: list[float | None]) -> float | None:
    """The most recent non-None value in an indicator series, or None if the
    series is empty or entirely None (insufficient history) — every strategy
    needs this, so it lives here instead of being copy-pasted six times."""
    for value in reversed(series):
        if value is not None:
            return value
    return None


def value_at(series: list[float | None], index: int) -> float | None:
    """The value at a specific candle index — used when comparing an
    indicator's value at a specific swing, not just "the latest"."""
    if 0 <= index < len(series):
        return series[index]
    return None


def classify_strength(confidence: float) -> SignalStrength:
    """Fixed, documented thresholds — no randomness, no learned cutoffs
    (Sprint 5 section 9). Applied identically by every strategy in this
    Sprint; a strategy's own docstring only needs to state its confidence
    formula, not re-derive these bands.

    confidence >= 0.85  -> STRONG
    confidence >= 0.65  -> MEDIUM
    otherwise           -> WEAK
    """
    if confidence >= 0.85:
        return SignalStrength.STRONG
    if confidence >= 0.65:
        return SignalStrength.MEDIUM
    return SignalStrength.WEAK


def _score(checks: list[ConditionCheck]) -> tuple[float, list[str], list[str]]:
    if not checks:
        return 0.0, [], []
    triggered = [c.name for c in checks if c.passed]
    failed = [c.name for c in checks if not c.passed]
    return len(triggered) / len(checks), triggered, failed


def decide_direction(
    bullish_checks: list[ConditionCheck],
    bearish_checks: list[ConditionCheck],
    *,
    min_confidence: float,
) -> tuple[SignalDirection, float, list[str], list[str]]:
    """The one decision rule shared by every strategy in this Sprint (each
    strategy only supplies the checks, not this logic): score each direction
    independently as (satisfied checks / total checks), then fire the
    direction that BOTH clears `min_confidence` AND strictly outscores the
    other side. Never both directions. Never a coin flip between two equally
    weak cases (a tie fires nothing).

    Returns (direction, confidence, triggered, failed) — on NONE, the
    triggered/failed lists are still the higher-scoring side's, so callers
    can always explain what almost happened (section 41, diagnostics).
    """
    bull_score, bull_triggered, bull_failed = _score(bullish_checks)
    bear_score, bear_triggered, bear_failed = _score(bearish_checks)

    if bull_score >= min_confidence and bull_score > bear_score:
        return SignalDirection.CALL, bull_score, bull_triggered, bull_failed
    if bear_score >= min_confidence and bear_score > bull_score:
        return SignalDirection.PUT, bear_score, bear_triggered, bear_failed

    if bull_score >= bear_score:
        return SignalDirection.NONE, bull_score, bull_triggered, bull_failed
    return SignalDirection.NONE, bear_score, bear_triggered, bear_failed


class Strategy(ABC):
    """Common contract for every strategy. A Strategy reads a
    StrategyContext and returns a StrategyEvaluation — it never touches a
    broker, an order, a provider, or SQL (enforced by
    tests/strategies/test_isolation.py, not just this docstring)."""

    name: ClassVar[str]
    compatible_regimes: ClassVar[frozenset[str]] = frozenset()

    def __init__(self, **parameters):
        merged = {**self.default_parameters(), **parameters}
        self.validate_parameters(merged)
        self.parameters = merged

    def default_parameters(self) -> dict:
        return {"min_confidence": DEFAULT_MIN_CONFIDENCE, "expiry_candles": 1}

    def validate_parameters(self, parameters: dict) -> None:
        if not 0.0 <= parameters["min_confidence"] <= 1.0:
            raise ValueError("min_confidence must be between 0.0 and 1.0")
        if parameters["expiry_candles"] <= 0:
            raise ValueError("expiry_candles must be > 0")

    def get_parameters(self) -> dict:
        return dict(self.parameters)

    def required_indicators(self) -> list[IndicatorRequest]:
        """Indicators this strategy needs precomputed into
        context.indicators, keyed by the same NAME_period1_period2... scheme
        as app.indicators.registry.result_key. Empty by default (Price Action
        needs none — section 28)."""
        return []

    def prepare(self, context: StrategyContext) -> None:
        """Optional hook for per-evaluation setup. No-op by default."""
        return None

    @abstractmethod
    def evaluate(self, context: StrategyContext) -> StrategyEvaluation:
        raise NotImplementedError

    def _build_evaluation(
        self,
        context: StrategyContext,
        *,
        direction: SignalDirection,
        confidence: float,
        triggered: list[str],
        failed: list[str],
        metadata: dict | None = None,
        diagnostics: list[str] | None = None,
    ) -> StrategyEvaluation:
        """Shared plumbing every strategy's evaluate() ends with: builds the
        Signal (only for CALL/PUT — never for NONE) with a deterministic id
        and the shared strength thresholds, and wraps it in a
        StrategyEvaluation."""
        signal = None
        if direction != SignalDirection.NONE:
            signal = Signal(
                id=f"{self.name}:{context.symbol}:{context.timeframe.value}:{context.timestamp.isoformat()}",
                strategy=self.name,
                symbol=context.symbol,
                timeframe=context.timeframe,
                timestamp=context.timestamp,
                direction=direction,
                strength=classify_strength(confidence),
                confidence=confidence,
                expiry_candles=self.parameters["expiry_candles"],
                conditions=list(triggered),
                metadata={**(metadata or {}), "parameters": self.get_parameters()},
            )

        return StrategyEvaluation(
            strategy=self.name,
            signal=signal,
            triggered_conditions=triggered,
            failed_conditions=failed,
            evaluated_at=datetime.now(timezone.utc),
            diagnostics=diagnostics or [],
        )

    def _insufficient_data(self, context: StrategyContext, reason: str) -> StrategyEvaluation:
        return StrategyEvaluation(
            strategy=self.name,
            signal=None,
            triggered_conditions=[],
            failed_conditions=[],
            evaluated_at=datetime.now(timezone.utc),
            diagnostics=[f"insufficient_data: {reason}"],
        )

    def _regime_check(self, context: StrategyContext) -> ConditionCheck:
        return ConditionCheck(
            name="regime_compatible",
            passed=context.market_snapshot.regime.value in self.compatible_regimes,
        )
