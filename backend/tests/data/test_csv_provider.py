import asyncio
from datetime import datetime, timezone

from app.data.providers.csv_provider import CSVProvider
from app.data.types import Timeframe
from tests.conftest import FIXTURES_DIR


def test_reads_valid_file_with_all_documented_cases():
    provider = CSVProvider(FIXTURES_DIR / "eurusd_m1_sample.csv")
    result = provider.normalize("EURUSD", Timeframe.M1)

    # 10 rows total, 1 is an unparseable timestamp -> 9 candles reach the Normalizer's output
    assert len(result.candles) == 9
    assert len(result.errors) == 1
    assert result.out_of_order_count == 1


def test_column_mapping_file_reads_correctly():
    mapping = {"timestamp": "from", "high": "max", "low": "min"}
    provider = CSVProvider(FIXTURES_DIR / "mapped_columns.csv", column_mapping=mapping)
    result = provider.normalize("EURUSD", Timeframe.M1)

    assert len(result.candles) == 2
    assert len(result.errors) == 0


def test_missing_column_reports_error_for_every_row():
    provider = CSVProvider(FIXTURES_DIR / "missing_column.csv")
    result = provider.normalize("EURUSD", Timeframe.M1)

    assert result.candles == []
    assert len(result.errors) == 1


def test_empty_csv_yields_no_candles_and_no_errors():
    provider = CSVProvider(FIXTURES_DIR / "empty.csv")
    result = provider.normalize("EURUSD", Timeframe.M1)

    assert result.candles == []
    assert result.errors == []


def test_get_candles_filters_by_range_and_survives_a_naive_row():
    provider = CSVProvider(FIXTURES_DIR / "eurusd_m1_sample.csv")
    start = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 1, 1, 10, 2, tzinfo=timezone.utc)

    candles = asyncio.run(provider.get_candles("EURUSD", Timeframe.M1, start, end))

    # 10:00, 10:01, 10:02, 10:02(dup) all fall in range; nothing before 10:00 or after 10:02
    assert len(candles) == 4
    assert all(start <= c.timestamp.replace(tzinfo=c.timestamp.tzinfo or timezone.utc) <= end for c in candles)
