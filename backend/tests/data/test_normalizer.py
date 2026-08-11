from decimal import Decimal

from app.data.normalizer import normalize_rows
from app.data.types import DataSource, Timeframe


def row(timestamp="2026-01-01T10:00:00Z", open_="1.10", high="1.11", low="1.09", close="1.105", volume="100"):
    return {"timestamp": timestamp, "open": open_, "high": high, "low": low, "close": close, "volume": volume}


def test_sorts_by_timestamp_ascending():
    rows = [row(timestamp="2026-01-01T10:02:00Z"), row(timestamp="2026-01-01T10:00:00Z"), row(timestamp="2026-01-01T10:01:00Z")]
    result = normalize_rows(rows, symbol="X", timeframe=Timeframe.M1, source=DataSource.CSV)
    minutes = [c.timestamp.minute for c in result.candles]
    assert minutes == [0, 1, 2]


def test_detects_out_of_order_input():
    rows = [row(timestamp="2026-01-01T10:02:00Z"), row(timestamp="2026-01-01T10:00:00Z")]
    result = normalize_rows(rows, symbol="X", timeframe=Timeframe.M1, source=DataSource.CSV)
    assert result.out_of_order_count == 1


def test_timestamp_becomes_utc_aware():
    result = normalize_rows([row()], symbol="X", timeframe=Timeframe.M1, source=DataSource.CSV)
    assert result.candles[0].timestamp.tzinfo is not None


def test_naive_timestamp_preserved_for_validator_to_catch():
    result = normalize_rows([row(timestamp="2026-01-01T10:00:00")], symbol="X", timeframe=Timeframe.M1, source=DataSource.CSV)
    assert len(result.candles) == 1
    assert result.candles[0].timestamp.tzinfo is None


def test_numeric_fields_become_decimal():
    result = normalize_rows([row(open_="1.2345")], symbol="X", timeframe=Timeframe.M1, source=DataSource.CSV)
    assert result.candles[0].open == Decimal("1.2345")


def test_missing_volume_is_none():
    r = row()
    r["volume"] = ""
    result = normalize_rows([r], symbol="X", timeframe=Timeframe.M1, source=DataSource.CSV)
    assert result.candles[0].volume is None


def test_column_mapping_renames_fields():
    mapped_row = {"from": "2026-01-01T10:00:00Z", "open": "1.10", "max": "1.11", "min": "1.09", "close": "1.105", "volume": "100"}
    mapping = {"timestamp": "from", "high": "max", "low": "min"}
    result = normalize_rows([mapped_row], symbol="X", timeframe=Timeframe.M1, source=DataSource.CSV, column_mapping=mapping)
    assert len(result.candles) == 1
    assert result.candles[0].high == Decimal("1.11")
    assert result.candles[0].low == Decimal("1.09")


def test_unparseable_timestamp_is_a_normalization_error_not_a_crash():
    result = normalize_rows([row(timestamp="not-a-timestamp")], symbol="X", timeframe=Timeframe.M1, source=DataSource.CSV)
    assert result.candles == []
    assert len(result.errors) == 1
    assert result.errors[0].row_index == 0


def test_missing_column_is_a_normalization_error():
    r = row()
    del r["close"]
    result = normalize_rows([r], symbol="X", timeframe=Timeframe.M1, source=DataSource.CSV)
    assert result.candles == []
    assert len(result.errors) == 1


def test_garbage_price_is_a_normalization_error():
    result = normalize_rows([row(open_="not-a-number")], symbol="X", timeframe=Timeframe.M1, source=DataSource.CSV)
    assert result.candles == []
    assert len(result.errors) == 1
