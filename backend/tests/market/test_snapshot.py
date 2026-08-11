from app.data.types import Timeframe
from app.market.snapshot import MarketParams, build_snapshot
from app.market.types import MarketDirection, MarketRegime, StructureState
from tests.market.conftest import BEARISH_CLOSES, BULLISH_CLOSES, make_candles


def test_empty_candles_give_a_fully_unknown_snapshot():
    snapshot = build_snapshot([], symbol="X", timeframe=Timeframe.M1)
    assert snapshot.structure_state == StructureState.UNKNOWN
    assert snapshot.direction == MarketDirection.UNKNOWN
    assert snapshot.regime == MarketRegime.UNKNOWN
    assert snapshot.timestamp is None
    assert snapshot.supports == []
    assert snapshot.resistances == []
    assert snapshot.structure_events == []


def test_bullish_dataset_produces_a_consistent_snapshot():
    candles = make_candles(BULLISH_CLOSES)
    snapshot = build_snapshot(candles, symbol="EURUSD", timeframe=Timeframe.M1)

    assert snapshot.symbol == "EURUSD"
    assert snapshot.timeframe == Timeframe.M1
    assert snapshot.timestamp == candles[-1].timestamp
    assert snapshot.structure_state == StructureState.BULLISH
    assert snapshot.direction == MarketDirection.BULLISH
    assert snapshot.regime == MarketRegime.TRENDING_BULLISH
    assert snapshot.latest_swing_high is not None
    assert snapshot.latest_swing_low is not None
    assert snapshot.latest_swing_high.price > snapshot.latest_swing_low.price


def test_bearish_dataset_produces_a_consistent_snapshot():
    candles = make_candles(BEARISH_CLOSES)
    snapshot = build_snapshot(candles, symbol="EURUSD", timeframe=Timeframe.M1)
    assert snapshot.structure_state == StructureState.BEARISH
    assert snapshot.direction == MarketDirection.BEARISH
    assert snapshot.regime == MarketRegime.TRENDING_BEARISH


def test_snapshot_timestamp_is_the_last_candles_timestamp_not_a_requested_one():
    candles = make_candles(BULLISH_CLOSES)
    snapshot = build_snapshot(candles, symbol="X", timeframe=Timeframe.M1)
    assert snapshot.timestamp == candles[-1].timestamp


def test_snapshot_uses_indicators_engine_not_a_reimplementation():
    # ATR/EMA come from app.indicators — sanity check that volatility_value and
    # trend_strength are populated once there's enough history (rather than
    # silently None due to a broken wiring). Uses a shorter EMA period than the
    # default so 22 candles is enough history for the slope calculation too.
    candles = make_candles(BULLISH_CLOSES)
    params = MarketParams(trend_ema_period=5, trend_slope_period=3)
    snapshot = build_snapshot(candles, symbol="X", timeframe=Timeframe.M1, params=params)
    assert snapshot.volatility_value is not None
    assert snapshot.trend_strength is not None
