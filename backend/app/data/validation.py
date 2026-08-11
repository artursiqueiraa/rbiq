from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum

from app.data.types import Candle

DEFAULT_FUTURE_TOLERANCE = timedelta(seconds=5)


class ValidationIssue(str, Enum):
    INVALID_OHLC = "INVALID_OHLC"
    INVALID_PRICE = "INVALID_PRICE"
    INVALID_TIMESTAMP = "INVALID_TIMESTAMP"
    FUTURE_TIMESTAMP = "FUTURE_TIMESTAMP"


@dataclass(frozen=True)
class ValidationResult:
    candle: Candle
    issues: tuple[ValidationIssue, ...]

    @property
    def is_valid(self) -> bool:
        return not self.issues


def _is_finite_positive(value: Decimal | None) -> bool:
    if value is None:
        return False
    return value.is_finite() and value > 0


def validate_prices(candle: Candle) -> bool:
    return all(
        _is_finite_positive(price)
        for price in (candle.open, candle.high, candle.low, candle.close)
    )


def validate_ohlc(candle: Candle) -> bool:
    o, h, l, c = candle.open, candle.high, candle.low, candle.close
    return h >= o and h >= c and h >= l and l <= o and l <= c and l <= h


def validate_timestamp(
    candle: Candle, *, future_tolerance: timedelta = DEFAULT_FUTURE_TOLERANCE
) -> tuple[bool, bool]:
    """Returns (has_known_timezone, is_within_future_tolerance)."""
    if candle.timestamp.tzinfo is None:
        return False, True

    now = datetime.now(timezone.utc)
    is_future_ok = candle.timestamp <= now + future_tolerance
    return True, is_future_ok


def validate_candle(
    candle: Candle, *, future_tolerance: timedelta = DEFAULT_FUTURE_TOLERANCE
) -> ValidationResult:
    issues: list[ValidationIssue] = []

    if not validate_prices(candle):
        issues.append(ValidationIssue.INVALID_PRICE)
    elif not validate_ohlc(candle):
        issues.append(ValidationIssue.INVALID_OHLC)

    has_tz, within_tolerance = validate_timestamp(candle, future_tolerance=future_tolerance)
    if not has_tz:
        issues.append(ValidationIssue.INVALID_TIMESTAMP)
    elif not within_tolerance:
        issues.append(ValidationIssue.FUTURE_TIMESTAMP)

    return ValidationResult(candle=candle, issues=tuple(issues))


def validate_candles(
    candles: list[Candle], *, future_tolerance: timedelta = DEFAULT_FUTURE_TOLERANCE
) -> list[ValidationResult]:
    return [validate_candle(c, future_tolerance=future_tolerance) for c in candles]
