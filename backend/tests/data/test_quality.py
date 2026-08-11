from datetime import datetime, timedelta, timezone

from app.data.quality import compute_quality_report, compute_quality_score, detect_gaps
from app.data.types import Timeframe

BASE = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)


def minutes(*offsets: int) -> list[datetime]:
    return [BASE + timedelta(minutes=m) for m in offsets]


def test_detect_gaps_finds_no_gap_in_contiguous_series():
    gap_info = detect_gaps(minutes(0, 1, 2, 3), Timeframe.M1)
    assert gap_info.count == 0
    assert gap_info.first_gap is None


def test_detect_gaps_finds_a_single_missing_interval():
    gap_info = detect_gaps(minutes(0, 1, 2, 5), Timeframe.M1)
    assert gap_info.count == 1
    assert gap_info.first_gap == BASE + timedelta(minutes=2)
    assert gap_info.last_gap == gap_info.first_gap


def test_detect_gaps_counts_multiple_separate_gaps():
    gap_info = detect_gaps(minutes(0, 1, 5, 6, 10), Timeframe.M1)
    assert gap_info.count == 2


def test_quality_score_is_100_for_perfect_data():
    score = compute_quality_score(total=10, valid=10, duplicates=0, gaps=0, out_of_order=0)
    assert score == 100.0


def test_quality_score_drops_with_invalid_candles():
    score = compute_quality_score(total=10, valid=6, duplicates=0, gaps=0, out_of_order=0)
    assert score == 60.0


def test_quality_score_never_negative():
    score = compute_quality_score(total=10, valid=0, duplicates=50, gaps=50, out_of_order=50)
    assert score >= 0.0


def test_compute_quality_report_matches_documented_fixture_shape():
    # Same shape as data/raw/test/eurusd_m1_sample.csv's expected result (see its README):
    # 6 valid candles out of 10 total rows, one gap between 10:02 and 10:05.
    timestamps = minutes(-1, 0, 1, 2, 2, 5)  # includes the duplicate at +2
    report = compute_quality_report(
        timestamps,
        symbol="EURUSD",
        timeframe=Timeframe.M1,
        total_candles=10,
        valid_candles=6,
        invalid_candles=4,
        duplicates=1,
        out_of_order=1,
    )
    assert report.total_candles == 10
    assert report.valid_candles == 6
    assert report.gaps == 1
    assert report.duplicates == 1
    assert report.out_of_order == 1
    assert 0 <= report.quality_score <= 100
