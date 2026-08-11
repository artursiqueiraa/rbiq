from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CandleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    timeframe: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None
    source: str


class DataQualityOut(BaseModel):
    symbol: str
    timeframe: str
    total_candles: int
    valid_candles: int
    invalid_candles: int
    duplicates: int
    gaps: int
    out_of_order: int
    first_gap: datetime | None
    last_gap: datetime | None
    last_timestamp: datetime | None
    quality_score: float


class ImportJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    source_file: str
    symbol: str
    timeframe: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    duplicates: int
    gaps: int


class ImportRequest(BaseModel):
    provider: str = "csv"
    file: str
    symbol: str
    timeframe: str
    column_mapping: dict[str, str] | None = None


class ImportResultOut(BaseModel):
    import_id: int
    status: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    duplicates: int
    inserted: int
    gaps: int
