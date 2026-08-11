from datetime import timedelta

import pytest

from app.data.types import Timeframe


def test_m1_m5_m15_values():
    assert Timeframe.M1.value == "M1"
    assert Timeframe.M5.value == "M5"
    assert Timeframe.M15.value == "M15"


def test_invalid_timeframe_value_rejected():
    with pytest.raises(ValueError):
        Timeframe("M2")


def test_duration_matches_timeframe():
    assert Timeframe.M1.duration == timedelta(minutes=1)
    assert Timeframe.M5.duration == timedelta(minutes=5)
    assert Timeframe.H1.duration == timedelta(hours=1)
    assert Timeframe.D1.duration == timedelta(days=1)
