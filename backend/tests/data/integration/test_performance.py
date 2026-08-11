import csv
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.data.ingestion import DataIngestionService
from app.data.types import Timeframe
from app.repositories.candle_repository import CandleRepository
from tests.data.integration.conftest import TEST_SYMBOL_PREFIX

SYMBOL = f"{TEST_SYMBOL_PREFIX}PERF"
ROW_COUNT = 100_000


def _write_synthetic_csv(path: Path, rows: int) -> None:
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for i in range(rows):
            ts = (start + timedelta(minutes=i)).isoformat().replace("+00:00", "Z")
            writer.writerow([ts, "1.1000", "1.1010", "1.0990", "1.1005", "100"])


def test_ingests_one_hundred_thousand_candles_and_reports_throughput(tmp_path, db_session):
    """Not a hard performance gate (per Sprint 2 scope, that's out of bounds) — this
    exists to surface obvious bottlenecks early, before the Indicators/Backtest
    engines start depending on this layer being fast enough to be usable."""
    csv_path = tmp_path / "synthetic_100k.csv"
    _write_synthetic_csv(csv_path, ROW_COUNT)

    service = DataIngestionService(db_session)

    started = time.perf_counter()
    result = service.ingest_csv(file_path=csv_path, symbol=SYMBOL, timeframe=Timeframe.M1)
    elapsed = time.perf_counter() - started

    assert result.status == "COMPLETED"
    assert result.inserted == ROW_COUNT

    candles_per_second = ROW_COUNT / elapsed if elapsed > 0 else float("inf")
    print(
        f"\n[performance] {ROW_COUNT} candles ingested in {elapsed:.2f}s "
        f"({candles_per_second:.0f} candles/sec)"
    )

    stored_count = CandleRepository(db_session).count(symbol=SYMBOL, timeframe=Timeframe.M1)
    assert stored_count == ROW_COUNT

    # Generous ceiling: this is a bottleneck smoke test, not a benchmark to optimize for.
    assert elapsed < 120
