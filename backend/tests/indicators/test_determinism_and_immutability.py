import pytest

from app.indicators import ATR, CCI, EMA, MACD, RSI, SMA, Bollinger, Stochastic
from tests.indicators.conftest import make_candles

CLOSES = [10, 11, 12, 9, 13, 14, 8, 15, 16, 12]
HIGHS = [c + 1 for c in CLOSES]
LOWS = [c - 1 for c in CLOSES]

FACTORIES = [
    lambda: SMA(period=3),
    lambda: EMA(period=3),
    lambda: RSI(period=3),
    lambda: MACD(fast_period=2, slow_period=3, signal_period=2),
    lambda: Bollinger(period=3),
    lambda: ATR(period=3),
    lambda: Stochastic(k_period=3, d_period=2, smooth=1),
    lambda: CCI(period=3),
]


@pytest.mark.parametrize("factory", FACTORIES, ids=[f().name for f in FACTORIES])
def test_calculation_is_deterministic(factory):
    candles = make_candles(CLOSES, highs=HIGHS, lows=LOWS)

    first = factory().calculate(candles)
    second = factory().calculate(candles)

    assert first.series.keys() == second.series.keys()
    for key in first.series:
        assert first.series[key] == second.series[key]


@pytest.mark.parametrize("factory", FACTORIES, ids=[f().name for f in FACTORIES])
def test_candles_are_not_mutated(factory):
    candles = make_candles(CLOSES, highs=HIGHS, lows=LOWS)
    candles_before = list(candles)  # frozen Candle objects -> a shallow copy is enough to compare

    factory().calculate(candles)

    assert candles == candles_before
    assert all(c1 is c2 for c1, c2 in zip(candles, candles_before))
