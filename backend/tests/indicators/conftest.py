from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.data.types import Candle, DataSource, Timeframe

BASE_TS = datetime(2026, 1, 1, tzinfo=timezone.utc)
TOLERANCE = 1e-6


def make_candles(
    closes: list[float],
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    opens: list[float] | None = None,
    timeframe: Timeframe = Timeframe.M1,
) -> list[Candle]:
    """Builds a minimal, valid, ascending-timestamp candle series from plain
    float lists. Defaults high/low/open to close when not given, for tests
    that only care about the close price."""
    highs = highs if highs is not None else closes
    lows = lows if lows is not None else closes
    opens = opens if opens is not None else closes

    return [
        Candle(
            symbol="TEST",
            timeframe=timeframe,
            timestamp=BASE_TS + timedelta(minutes=i),
            open=Decimal(str(opens[i])),
            high=Decimal(str(highs[i])),
            low=Decimal(str(lows[i])),
            close=Decimal(str(closes[i])),
            volume=None,
            source=DataSource.CSV,
        )
        for i in range(len(closes))
    ]


def assert_series_close(actual: list[float | None], expected: list[float | None], tolerance: float = TOLERANCE):
    assert len(actual) == len(expected), f"length mismatch: {len(actual)} != {len(expected)}"
    for i, (a, e) in enumerate(zip(actual, expected)):
        if e is None:
            assert a is None, f"index {i}: expected None, got {a}"
        else:
            assert a is not None, f"index {i}: expected {e}, got None"
            assert abs(a - e) < tolerance, f"index {i}: expected {e}, got {a}"
