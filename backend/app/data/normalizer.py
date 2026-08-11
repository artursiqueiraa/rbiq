from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from app.data.timeutils import to_comparable_utc
from app.data.types import Candle, DataSource, Timeframe

DEFAULT_COLUMN_MAPPING = {
    "timestamp": "timestamp",
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "volume": "volume",
}


@dataclass(frozen=True)
class NormalizationError:
    row_index: int
    reason: str
    raw_row: dict


@dataclass(frozen=True)
class NormalizationResult:
    candles: list[Candle]
    errors: list[NormalizationError] = field(default_factory=list)
    out_of_order_count: int = 0


def _parse_timestamp(raw: str) -> datetime:
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        # Preserved naive on purpose: the Validator flags this as INVALID_TIMESTAMP
        # rather than the Normalizer silently guessing a timezone.
        return parsed
    return parsed.astimezone(timezone.utc)


def _parse_decimal(raw: str) -> Decimal:
    text = raw.strip()
    if text == "":
        raise ValueError("empty numeric value")
    value = Decimal(text)
    if not value.is_finite():
        raise ValueError(f"non-finite numeric value: {raw!r}")
    return value


def _count_out_of_order(timestamps: list[datetime]) -> int:
    count = 0
    for previous, current in zip(timestamps, timestamps[1:]):
        if to_comparable_utc(current) < to_comparable_utc(previous):
            count += 1
    return count


def normalize_rows(
    raw_rows: list[dict],
    *,
    symbol: str,
    timeframe: Timeframe,
    source: DataSource,
    column_mapping: dict[str, str] | None = None,
) -> NormalizationResult:
    """Turn raw provider rows into canonical (but not yet validated) Candles.

    Rows that cannot even be parsed (missing column, garbage number, unparsable
    timestamp) are reported as NormalizationError and dropped from the output —
    they never reach the database. Rows that parse but contain semantically bad
    data (e.g. high < low, a naive timestamp) are still returned as Candles: that
    kind of problem is the Validator's job to catch, not the Normalizer's.
    """
    mapping = {**DEFAULT_COLUMN_MAPPING, **(column_mapping or {})}

    candles: list[Candle] = []
    errors: list[NormalizationError] = []

    for index, row in enumerate(raw_rows):
        try:
            timestamp = _parse_timestamp(row[mapping["timestamp"]])
            open_ = _parse_decimal(row[mapping["open"]])
            high = _parse_decimal(row[mapping["high"]])
            low = _parse_decimal(row[mapping["low"]])
            close = _parse_decimal(row[mapping["close"]])

            volume_raw = row.get(mapping["volume"])
            volume = (
                _parse_decimal(volume_raw)
                if volume_raw not in (None, "")
                else None
            )
        except (KeyError, ValueError, InvalidOperation) as exc:
            errors.append(NormalizationError(row_index=index, reason=str(exc), raw_row=row))
            continue

        candles.append(
            Candle(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=timestamp,
                open=open_,
                high=high,
                low=low,
                close=close,
                volume=volume,
                source=source,
            )
        )

    out_of_order_count = _count_out_of_order([c.timestamp for c in candles])
    candles.sort(key=lambda c: to_comparable_utc(c.timestamp))

    return NormalizationResult(candles=candles, errors=errors, out_of_order_count=out_of_order_count)
