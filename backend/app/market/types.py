from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from app.data.types import Timeframe


class SwingType(str, Enum):
    HIGH = "HIGH"
    LOW = "LOW"


@dataclass(frozen=True)
class SwingPoint:
    """A confirmed local extreme. `timestamp` is when it happened (the extreme
    candle's own timestamp); `confirmation_timestamp` is when enough later
    candles existed to confirm it was in fact a swing. The two are only equal
    when right_bars == 0 — for any real confirmation window they differ, and
    nothing in this codebase is allowed to pretend it knew about a swing before
    its confirmation_timestamp."""

    type: SwingType
    timestamp: datetime
    confirmation_timestamp: datetime
    price: Decimal
    index: int
    strength: float


class StructureState(str, Enum):
    UNKNOWN = "UNKNOWN"
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    RANGE = "RANGE"
    TRANSITION = "TRANSITION"


class StructureEventType(str, Enum):
    SWING_HIGH_CONFIRMED = "SWING_HIGH_CONFIRMED"
    SWING_LOW_CONFIRMED = "SWING_LOW_CONFIRMED"
    HIGHER_HIGH = "HIGHER_HIGH"
    HIGHER_LOW = "HIGHER_LOW"
    LOWER_HIGH = "LOWER_HIGH"
    LOWER_LOW = "LOWER_LOW"
    STRUCTURE_BREAK = "STRUCTURE_BREAK"
    STRUCTURE_CHANGE = "STRUCTURE_CHANGE"


@dataclass(frozen=True)
class StructureEvent:
    event_type: StructureEventType
    timestamp: datetime
    confirmation_timestamp: datetime
    price: Decimal
    metadata: dict = field(default_factory=dict)


class ZoneKind(str, Enum):
    SUPPORT = "SUPPORT"
    RESISTANCE = "RESISTANCE"


@dataclass(frozen=True)
class Zone:
    """A support or resistance region, not a single exact price — built by
    clustering nearby confirmed swing points (see support_resistance.py)."""

    kind: ZoneKind
    price: Decimal
    lower_bound: Decimal
    upper_bound: Decimal
    touches: int
    strength: float
    first_seen: datetime
    last_seen: datetime


class MarketDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


class VolatilityRegime(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


class MarketRegime(str, Enum):
    TRENDING_BULLISH = "TRENDING_BULLISH"
    TRENDING_BEARISH = "TRENDING_BEARISH"
    RANGING = "RANGING"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    TRANSITION = "TRANSITION"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class MarketSnapshot:
    """The contract between the Market Engine and whatever consumes it later
    (a future Strategy Engine). Describes market STATE only — nothing here
    ever says "enter" or "exit"."""

    symbol: str
    timeframe: Timeframe
    timestamp: datetime
    direction: MarketDirection
    structure_state: StructureState
    regime: MarketRegime
    volatility: VolatilityRegime
    volatility_value: float | None
    trend_strength: float | None
    latest_swing_high: SwingPoint | None
    latest_swing_low: SwingPoint | None
    supports: list[Zone]
    resistances: list[Zone]
    structure_events: list[StructureEvent]
