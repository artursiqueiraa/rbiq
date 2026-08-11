from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from app.data.types import Timeframe


class SignalDirection(str, Enum):
    CALL = "CALL"
    PUT = "PUT"
    NONE = "NONE"


class SignalStrength(str, Enum):
    WEAK = "WEAK"
    MEDIUM = "MEDIUM"
    STRONG = "STRONG"


@dataclass(frozen=True)
class Signal:
    """A research signal — a direction a strategy considers worth studying,
    nothing more. `id` is deterministic (strategy+symbol+timeframe+timestamp),
    not random, so two evaluations of the same context produce byte-identical
    signals (see the determinism tests). CALL/PUT here mean signal direction
    only; nothing in this codebase sends an order because of this object."""

    id: str
    strategy: str
    symbol: str
    timeframe: Timeframe
    timestamp: datetime
    direction: SignalDirection
    strength: SignalStrength
    confidence: float
    expiry_candles: int
    conditions: list[str]
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class StrategyEvaluation:
    """What a strategy hands back for EVERY evaluation, whether or not a
    signal fired. `signal` is None when nothing fired — direction NONE never
    appears on a constructed Signal object, only as an internal intermediate
    value (see base.decide_direction).

    `evaluated_at` is a wall-clock audit stamp (when the computation ran),
    not part of the decision itself — it is deliberately excluded from the
    determinism tests (section 59), which compare everything else. Two calls
    to evaluate() with the same context always produce the same signal and
    conditions; they will not have the same evaluated_at.
    """

    strategy: str
    signal: Signal | None
    triggered_conditions: list[str]
    failed_conditions: list[str]
    evaluated_at: datetime
    diagnostics: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class IndicatorRequest:
    """What a strategy asks StrategyService to precompute into
    StrategyContext.indicators before evaluate() runs."""

    name: str
    parameters: dict = field(default_factory=dict)
