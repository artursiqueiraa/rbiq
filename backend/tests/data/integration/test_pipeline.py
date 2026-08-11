from fastapi.testclient import TestClient

from app.data.ingestion import DataIngestionService
from app.data.types import Timeframe
from app.main import app
from app.repositories.import_repository import ImportRepository
from tests.conftest import FIXTURES_DIR
from tests.data.integration.conftest import TEST_SYMBOL_PREFIX

SYMBOL = f"{TEST_SYMBOL_PREFIX}EURUSD"
client = TestClient(app)


def test_full_pipeline_csv_to_postgres_matches_documented_fixture(db_session):
    """CSV -> CSVProvider -> Normalizer -> Validator -> CandleRepository -> PostgreSQL,
    end to end against the real database, using the counts documented in
    data/raw/test/README.md for eurusd_m1_sample.csv."""
    service = DataIngestionService(db_session)
    result = service.ingest_csv(file_path=FIXTURES_DIR / "eurusd_m1_sample.csv", symbol=SYMBOL, timeframe=Timeframe.M1)

    assert result.status == "PARTIAL"  # some rows are invalid by design in this fixture
    assert result.total_rows == 10
    assert result.valid_rows == 6
    assert result.invalid_rows == 4
    assert result.duplicates == 1
    assert result.inserted == 5
    assert result.quality.gaps == 1

    import_history = ImportRepository(db_session).list_recent(limit=5)
    assert any(record.id == result.import_id and record.status == "PARTIAL" for record in import_history)


def test_import_and_query_via_api(db_session):
    file_path = str((FIXTURES_DIR / "eurusd_m1_sample.csv").relative_to(FIXTURES_DIR.parents[2]))

    import_response = client.post(
        "/api/data/import",
        json={"provider": "csv", "file": file_path, "symbol": SYMBOL, "timeframe": "M1"},
    )
    assert import_response.status_code == 200
    body = import_response.json()
    assert body["inserted"] == 5

    candles_response = client.get("/api/candles", params={"symbol": SYMBOL, "timeframe": "M1"})
    assert candles_response.status_code == 200
    candles = candles_response.json()
    assert len(candles) == 5

    quality_response = client.get("/api/candles/quality", params={"symbol": SYMBOL, "timeframe": "M1"})
    assert quality_response.status_code == 200
    quality = quality_response.json()
    assert quality["total_candles"] == 5
    assert quality["gaps"] == 1


def test_import_rejects_path_traversal():
    response = client.post(
        "/api/data/import",
        json={"provider": "csv", "file": "../../etc/passwd", "symbol": SYMBOL, "timeframe": "M1"},
    )
    assert response.status_code == 400


def test_import_rejects_file_outside_data_raw():
    response = client.post(
        "/api/data/import",
        json={"provider": "csv", "file": "backend/pyproject.toml", "symbol": SYMBOL, "timeframe": "M1"},
    )
    assert response.status_code == 400
