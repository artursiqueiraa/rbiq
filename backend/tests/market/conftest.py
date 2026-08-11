from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.data.types import Candle, DataSource, Timeframe

BASE_TS = datetime(2026, 1, 1, tzinfo=timezone.utc)

# Hand-designed candle set with a clean, unambiguous HH+HL bullish structure,
# verified by actually running detect_swings()/analyze_structure() against it
# (see the Sprint 4 report, "Problemas encontrados") rather than trusting hand
# arithmetic alone:
#
#   index 0-5   rise to a local peak at index 5  (close=15)
#   index 6-8   decline (confirms the peak as a swing high at index 5)
#   index 9-13  rise past the previous peak to a new peak at index 13 (close=22)
#   index 14-16 decline to a higher low than the first one (confirms swing low
#               at index 16, and the swing high at index 13)
#   index 17-21 rise again
#
# With left_bars=2, right_bars=2 this produces exactly 4 confirmed swings:
#   HIGH @ 5  (15.5)   LOW @ 8  (11.5)   HIGH @ 13 (22.5)   LOW @ 16 (16.5)
# which is a textbook HH (22.5 > 15.5) + HL (16.5 > 11.5) -> BULLISH.
BULLISH_CLOSES = [10, 11, 12, 13, 14, 15, 14, 13, 12, 14, 16, 18, 20, 22, 20, 18, 17, 19, 21, 23, 25, 27]

# Mirror image of the above (37 - x flips every peak into a trough and vice
# versa, keeping prices positive): LL + LH -> BEARISH. Verified the same way.
BEARISH_CLOSES = [37 - c for c in BULLISH_CLOSES]

# Repeating triangle wave hitting the exact same peak (15) and trough (10)
# three times -> EQUAL high_trend/low_trend -> RANGE. Verified.
RANGE_CLOSES = [10, 11, 12, 13, 14, 15, 14, 13, 12, 11, 10, 11, 12, 13, 14, 15, 14, 13, 12, 11, 10, 11, 12, 13, 14, 15]

# The bullish dataset, then a sharp decline that closes below the last
# confirmed higher-low (16.5) -> STRUCTURE_BREAK, state moves to TRANSITION.
# Verified.
BREAK_CLOSES = BULLISH_CLOSES + [24, 20, 14, 10, 8, 8, 8]


def make_candles(
    closes: list[float],
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    timeframe: Timeframe = Timeframe.M1,
    symbol: str = "TEST",
) -> list[Candle]:
    highs = highs if highs is not None else [c + 0.5 for c in closes]
    lows = lows if lows is not None else [c - 0.5 for c in closes]

    return [
        Candle(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=BASE_TS + timedelta(minutes=i),
            open=Decimal(str(closes[i])),
            high=Decimal(str(highs[i])),
            low=Decimal(str(lows[i])),
            close=Decimal(str(closes[i])),
            volume=None,
            source=DataSource.CSV,
        )
        for i in range(len(closes))
    ]
