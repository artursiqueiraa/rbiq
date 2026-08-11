from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.market.structure.support_resistance import detect_zones
from app.market.types import SwingPoint, SwingType, ZoneKind

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def swing(price, type_, index):
    return SwingPoint(
        type=type_,
        timestamp=BASE + timedelta(minutes=index),
        confirmation_timestamp=BASE + timedelta(minutes=index + 2),
        price=Decimal(str(price)),
        index=index,
        strength=1.0,
    )


def test_empty_input():
    assert detect_zones([]) == []


def test_isolated_swings_become_separate_zones():
    swings = [
        swing(100, SwingType.LOW, 0),
        swing(200, SwingType.LOW, 10),  # far away, well beyond any reasonable tolerance
    ]
    zones = detect_zones(swings, tolerance_pct=0.001)
    supports = [z for z in zones if z.kind == ZoneKind.SUPPORT]
    assert len(supports) == 2
    assert all(z.touches == 1 for z in supports)


def test_nearby_swings_are_grouped_into_one_zone():
    swings = [
        swing(100.00, SwingType.LOW, 0),
        swing(100.05, SwingType.LOW, 5),
        swing(100.08, SwingType.LOW, 10),
    ]
    zones = detect_zones(swings, tolerance_pct=0.01)  # 1% of ~100 = 1.0, easily covers this spread
    supports = [z for z in zones if z.kind == ZoneKind.SUPPORT]
    assert len(supports) == 1
    assert supports[0].touches == 3
    assert supports[0].lower_bound == Decimal("100.00")
    assert supports[0].upper_bound == Decimal("100.08")


def test_highs_and_lows_are_kept_separate():
    swings = [
        swing(100, SwingType.LOW, 0),
        swing(100, SwingType.HIGH, 1),
    ]
    zones = detect_zones(swings, tolerance_pct=0.5)
    assert {z.kind for z in zones} == {ZoneKind.SUPPORT, ZoneKind.RESISTANCE}


def test_more_touches_and_more_recent_gives_higher_strength():
    early_only = [swing(100, SwingType.LOW, 0), swing(100, SwingType.LOW, 1)]
    late_and_frequent = [
        swing(100, SwingType.LOW, 0),
        swing(100, SwingType.LOW, 1),
        swing(100, SwingType.LOW, 2),
        swing(100, SwingType.LOW, 50),
    ]
    zone_a = detect_zones(early_only, tolerance_pct=0.5)[0]
    zone_b = detect_zones(late_and_frequent, tolerance_pct=0.5)[0]
    assert zone_b.strength > zone_a.strength


def test_zone_price_is_the_mean_of_its_touches():
    swings = [swing(100, SwingType.LOW, 0), swing(102, SwingType.LOW, 1)]
    zones = detect_zones(swings, tolerance_pct=0.5)
    assert zones[0].price == Decimal("101")


def test_rejects_negative_tolerance():
    with pytest.raises(ValueError):
        detect_zones([swing(100, SwingType.LOW, 0)], tolerance_pct=-0.1)
