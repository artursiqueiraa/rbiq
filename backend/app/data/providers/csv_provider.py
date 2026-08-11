import csv
from datetime import datetime
from pathlib import Path

from app.data.normalizer import NormalizationResult, normalize_rows
from app.data.providers.base import DataProvider
from app.data.timeutils import to_comparable_utc
from app.data.types import Candle, DataSource, Timeframe


class CSVProvider(DataProvider):
    """Reads candles from a CSV file with a configurable column mapping.

    The file is expected to hold a single symbol/timeframe (the common case for
    historical dataset exports). Column names can differ from the canonical ones
    (e.g. "from" instead of "timestamp") via `column_mapping`.
    """

    def __init__(self, file_path: str | Path, column_mapping: dict[str, str] | None = None):
        self.file_path = Path(file_path)
        self.column_mapping = column_mapping

    def read_raw_rows(self) -> list[dict]:
        with self.file_path.open(newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def normalize(
        self, symbol: str, timeframe: Timeframe, source: DataSource = DataSource.CSV
    ) -> NormalizationResult:
        raw_rows = self.read_raw_rows()
        return normalize_rows(
            raw_rows,
            symbol=symbol,
            timeframe=timeframe,
            source=source,
            column_mapping=self.column_mapping,
        )

    async def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        result = self.normalize(symbol, timeframe)
        return [c for c in result.candles if start <= to_comparable_utc(c.timestamp) <= end]
