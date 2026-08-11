from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from app.data.types import Timeframe


@dataclass(frozen=True)
class GapInfo:
    count: int
    first_gap: datetime | None
    last_gap: datetime | None


@dataclass(frozen=True)
class DataQualityReport:
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


def detect_gaps(sorted_timestamps: Sequence[datetime], timeframe: Timeframe) -> GapInfo:
    """Compares consecutive timestamps against the timeframe's expected step.
    `sorted_timestamps` must already be in ascending order — this function does
    not sort, since callers usually already have (or want) that guarantee explicit.
    """
    step = timeframe.duration
    gap_starts: list[datetime] = []

    for previous, current in zip(sorted_timestamps, sorted_timestamps[1:]):
        if current - previous > step:
            gap_starts.append(previous)

    if not gap_starts:
        return GapInfo(count=0, first_gap=None, last_gap=None)

    return GapInfo(count=len(gap_starts), first_gap=gap_starts[0], last_gap=gap_starts[-1])


def compute_quality_score(
    *, total: int, valid: int, duplicates: int, gaps: int, out_of_order: int
) -> float:
    """100 = no problems found. Each category subtracts from the valid ratio, capped
    so no single category can dominate the score by itself. This is a research aid
    for spotting datasets that need investigation — not a statistic to optimize."""
    if total == 0:
        return 100.0

    valid_ratio = valid / total
    score = 100 * valid_ratio
    score -= min(gaps, 10)
    score -= min(duplicates, 5)
    score -= min(out_of_order, 5)
    return round(max(0.0, min(100.0, score)), 1)


def compute_quality_report(
    timestamps: Sequence[datetime],
    *,
    symbol: str,
    timeframe: Timeframe | str,
    total_candles: int | None = None,
    valid_candles: int | None = None,
    invalid_candles: int = 0,
    duplicates: int = 0,
    out_of_order: int = 0,
) -> DataQualityReport:
    tf = timeframe if isinstance(timeframe, Timeframe) else Timeframe(timeframe)

    total = total_candles if total_candles is not None else len(timestamps)
    valid = valid_candles if valid_candles is not None else len(timestamps)

    sorted_timestamps = sorted(timestamps)
    gap_info = detect_gaps(sorted_timestamps, tf) if sorted_timestamps else GapInfo(0, None, None)

    score = compute_quality_score(
        total=total, valid=valid, duplicates=duplicates, gaps=gap_info.count, out_of_order=out_of_order
    )

    return DataQualityReport(
        symbol=symbol,
        timeframe=tf.value,
        total_candles=total,
        valid_candles=valid,
        invalid_candles=invalid_candles,
        duplicates=duplicates,
        gaps=gap_info.count,
        out_of_order=out_of_order,
        first_gap=gap_info.first_gap,
        last_gap=gap_info.last_gap,
        last_timestamp=sorted_timestamps[-1] if sorted_timestamps else None,
        quality_score=score,
    )
