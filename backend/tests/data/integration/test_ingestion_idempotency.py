from app.data.ingestion import DataIngestionService
from app.data.types import Timeframe
from app.repositories.candle_repository import CandleRepository
from tests.conftest import FIXTURES_DIR
from tests.data.integration.conftest import TEST_SYMBOL_PREFIX

SYMBOL = f"{TEST_SYMBOL_PREFIX}EURUSD"


def test_importing_the_same_file_twice_does_not_duplicate_rows(db_session):
    service = DataIngestionService(db_session)
    file_path = FIXTURES_DIR / "eurusd_m1_sample.csv"

    first = service.ingest_csv(file_path=file_path, symbol=SYMBOL, timeframe=Timeframe.M1)
    assert first.inserted == 5
    assert first.duplicates == 1  # the in-file duplicate at 10:02:00Z

    second = service.ingest_csv(file_path=file_path, symbol=SYMBOL, timeframe=Timeframe.M1)
    assert second.inserted == 0
    assert second.duplicates == second.valid_rows  # everything valid already existed

    stored_count = CandleRepository(db_session).count(symbol=SYMBOL, timeframe=Timeframe.M1)
    assert stored_count == 5
