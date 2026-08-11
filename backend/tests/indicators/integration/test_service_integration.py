from datetime import datetime, timedelta, timezone

from app.data.types import Timeframe
from app.indicators.service import IndicatorService
from tests.indicators.integration.conftest import BASE_TS, TEST_SYMBOL_PREFIX, seed_candles

SYMBOL = f"{TEST_SYMBOL_PREFIX}IND_SERVICE"


def test_full_pipeline_postgres_to_indicator_result(db_session):
    """PostgreSQL -> CandleRepository -> IndicatorService -> IndicatorRegistry
    -> Indicator, against the real database."""
    closes = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]
    seed_candles(db_session, SYMBOL, closes)

    service = IndicatorService(db_session)
    result = service.calculate(
        symbol=SYMBOL,
        timeframe=Timeframe.M1,
        start=BASE_TS,
        end=BASE_TS + timedelta(minutes=len(closes)),
        indicator_specs=[
            {"name": "SMA", "parameters": {"period": 3}},
            {"name": "RSI", "parameters": {"period": 3}},
        ],
    )

    assert len(result.timestamps) == len(closes)
    assert result.closes == [float(c) for c in closes]
    assert set(result.indicators.keys()) == {"SMA_3", "RSI_3"}
    assert result.indicators["SMA_3"].series["value"][-1] == 18.0  # mean(17,18,19)


def test_unknown_indicator_name_raises_value_error(db_session):
    seed_candles(db_session, SYMBOL, [10, 11, 12])
    service = IndicatorService(db_session)

    try:
        service.calculate(
            symbol=SYMBOL,
            timeframe=Timeframe.M1,
            start=BASE_TS,
            end=BASE_TS + timedelta(minutes=3),
            indicator_specs=[{"name": "NOT_REAL", "parameters": {}}],
        )
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_empty_symbol_returns_empty_series_not_an_error(db_session):
    service = IndicatorService(db_session)
    result = service.calculate(
        symbol=f"{TEST_SYMBOL_PREFIX}DOES_NOT_EXIST",
        timeframe=Timeframe.M1,
        start=BASE_TS,
        end=BASE_TS + timedelta(days=1),
        indicator_specs=[{"name": "EMA", "parameters": {"period": 20}}],
    )
    assert result.timestamps == []
    assert result.indicators["EMA_20"].series["value"] == []
