from app.data.types import Timeframe
from app.market.service import MarketService
from tests.market.conftest import BULLISH_CLOSES
from tests.market.integration.conftest import BASE_TS, TEST_SYMBOL_PREFIX, seed_candles

SYMBOL = f"{TEST_SYMBOL_PREFIX}MARKET_SERVICE"


def test_full_pipeline_postgres_to_market_snapshot(db_session):
    """PostgreSQL -> CandleRepository -> MarketService -> swings -> structure
    -> regime -> MarketSnapshot, against the real database."""
    candles = seed_candles(db_session, SYMBOL, BULLISH_CLOSES)

    service = MarketService(db_session)
    snapshot = service.get_snapshot(symbol=SYMBOL, timeframe=Timeframe.M1, timestamp=candles[-1].timestamp)

    assert snapshot.symbol == SYMBOL
    assert snapshot.structure_state.value == "BULLISH"
    assert snapshot.direction.value == "BULLISH"
    assert snapshot.latest_swing_high is not None
    assert snapshot.latest_swing_low is not None


def test_snapshot_at_an_earlier_timestamp_only_sees_earlier_candles(db_session):
    """The causality guarantee, but through the real DB round-trip: asking for
    a snapshot at an earlier timestamp must not see swings confirmed later."""
    candles = seed_candles(db_session, SYMBOL, BULLISH_CLOSES)

    early_timestamp = candles[10].timestamp  # before the second swing (idx13) is confirmed (idx15)
    late_timestamp = candles[-1].timestamp

    service = MarketService(db_session)
    early_snapshot = service.get_snapshot(symbol=SYMBOL, timeframe=Timeframe.M1, timestamp=early_timestamp)
    late_snapshot = service.get_snapshot(symbol=SYMBOL, timeframe=Timeframe.M1, timestamp=late_timestamp)

    assert early_snapshot.structure_state.value == "UNKNOWN"  # only one swing high confirmed by then
    assert late_snapshot.structure_state.value == "BULLISH"


def test_structure_history_endpoint_service(db_session):
    candles = seed_candles(db_session, SYMBOL, BULLISH_CLOSES)
    service = MarketService(db_session)

    analysis = service.get_structure_history(
        symbol=SYMBOL, timeframe=Timeframe.M1, start=BASE_TS, end=candles[-1].timestamp
    )
    assert analysis.state.value == "BULLISH"
    assert len(analysis.confirmed_highs) == 2
    assert len(analysis.confirmed_lows) == 2


def test_empty_symbol_gives_unknown_snapshot_not_an_error(db_session):
    service = MarketService(db_session)
    snapshot = service.get_snapshot(
        symbol=f"{TEST_SYMBOL_PREFIX}DOES_NOT_EXIST", timeframe=Timeframe.M1, timestamp=BASE_TS
    )
    assert snapshot.structure_state.value == "UNKNOWN"
