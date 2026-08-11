from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.data.types import Candle, DataSource, Timeframe
from app.data.validation import ValidationIssue, validate_candle

UTC_NOW = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)


def make_candle(**overrides) -> Candle:
    defaults = dict(
        symbol="EURUSD",
        timeframe=Timeframe.M1,
        timestamp=UTC_NOW,
        open=Decimal("1.1000"),
        high=Decimal("1.1010"),
        low=Decimal("1.0990"),
        close=Decimal("1.1005"),
        source=DataSource.CSV,
        volume=Decimal("100"),
    )
    defaults.update(overrides)
    return Candle(**defaults)


def test_valid_candle_has_no_issues():
    result = validate_candle(make_candle())
    assert result.is_valid
    assert result.issues == ()


def test_ohlc_high_below_low_is_invalid():
    result = validate_candle(make_candle(high=Decimal("1.00"), low=Decimal("1.05")))
    assert ValidationIssue.INVALID_OHLC in result.issues


def test_ohlc_high_below_open_is_invalid():
    result = validate_candle(make_candle(open=Decimal("1.20"), high=Decimal("1.10")))
    assert ValidationIssue.INVALID_OHLC in result.issues


def test_zero_price_is_invalid():
    result = validate_candle(make_candle(close=Decimal("0")))
    assert ValidationIssue.INVALID_PRICE in result.issues


def test_negative_price_is_invalid():
    result = validate_candle(make_candle(open=Decimal("-1.10")))
    assert ValidationIssue.INVALID_PRICE in result.issues


def test_naive_timestamp_is_invalid():
    result = validate_candle(make_candle(timestamp=datetime(2026, 1, 1, 10, 0)))
    assert ValidationIssue.INVALID_TIMESTAMP in result.issues


def test_future_timestamp_beyond_tolerance_is_flagged():
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    result = validate_candle(make_candle(timestamp=future), future_tolerance=timedelta(seconds=5))
    assert ValidationIssue.FUTURE_TIMESTAMP in result.issues


def test_future_timestamp_within_tolerance_is_accepted():
    near_future = datetime.now(timezone.utc) + timedelta(seconds=2)
    result = validate_candle(make_candle(timestamp=near_future), future_tolerance=timedelta(seconds=5))
    assert ValidationIssue.FUTURE_TIMESTAMP not in result.issues
