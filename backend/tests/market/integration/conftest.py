from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.data.types import Candle, DataSource, Timeframe
from app.database.session import SessionLocal
from app.repositories.candle_repository import CandleRepository

TEST_SYMBOL_PREFIX = "TEST_"
BASE_TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _cleanup_test_data():
    yield
    session = SessionLocal()
    try:
        session.execute(text("DELETE FROM candles WHERE symbol LIKE :prefix"), {"prefix": f"{TEST_SYMBOL_PREFIX}%"})
        session.commit()
    finally:
        session.close()


def seed_candles(db_session, symbol: str, closes: list[float], timeframe: Timeframe = Timeframe.M1) -> list[Candle]:
    candles = [
        Candle(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=BASE_TS + timedelta(minutes=i),
            open=Decimal(str(c)),
            high=Decimal(str(c + 0.5)),
            low=Decimal(str(c - 0.5)),
            close=Decimal(str(c)),
            volume=None,
            source=DataSource.CSV,
        )
        for i, c in enumerate(closes)
    ]
    CandleRepository(db_session).bulk_insert(candles)
    return candles
