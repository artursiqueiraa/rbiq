from decimal import Decimal

from app.market.types import SwingPoint, SwingType, Zone, ZoneKind

DEFAULT_TOLERANCE_PCT = 0.001  # 0.1% of price — relative, not a fixed absolute number (Sprint 4 section 53)


def detect_zones(swings: list[SwingPoint], *, tolerance_pct: float = DEFAULT_TOLERANCE_PCT) -> list[Zone]:
    """Groups confirmed swing lows into SUPPORT zones and confirmed swing highs
    into RESISTANCE zones. Swings within `tolerance_pct` of each other (relative
    to price, so it scales with the asset instead of assuming EURUSD-sized
    numbers) are merged into the same zone instead of creating one zone per
    swing.

    Algorithm: sort candidate swings by price, then greedily group consecutive
    swings while each new swing's price is within `tolerance_pct` of the
    RUNNING GROUP's own price range (so a slow drift across many swings can't
    chain into one enormous zone — each addition is checked against the
    group's current bounds, not just the previous single swing).

    strength = touches * (1 + recency), where recency is how late the zone's
    last touch happened relative to the full swing set's time span (0 = the
    zone's last touch is the earliest confirmation in the set, 1 = the most
    recent). A zone tested many times, tested recently, scores higher than one
    tested once long ago — both factors the Sprint explicitly asks for
    (section 20), combined into one documented formula.
    """
    if tolerance_pct < 0:
        raise ValueError("tolerance_pct must be >= 0")

    highs = sorted((s for s in swings if s.type == SwingType.HIGH), key=lambda s: s.price)
    lows = sorted((s for s in swings if s.type == SwingType.LOW), key=lambda s: s.price)

    all_confirmations = [s.confirmation_timestamp for s in swings]
    earliest = min(all_confirmations) if all_confirmations else None
    latest = max(all_confirmations) if all_confirmations else None

    zones = _cluster(highs, ZoneKind.RESISTANCE, tolerance_pct, earliest, latest)
    zones += _cluster(lows, ZoneKind.SUPPORT, tolerance_pct, earliest, latest)
    return zones


def _cluster(sorted_swings: list[SwingPoint], kind: ZoneKind, tolerance_pct: float, earliest, latest) -> list[Zone]:
    """`sorted_swings` is price-sorted, so a group's low/high are always its
    first/last member — tracked as running values instead of re-scanning the
    whole group on every addition. That distinction matters: recomputing
    min()/max() over the group on each append is O(group size) per step, which
    made this O(n^2) on real 100k-candle inputs where one drifting price
    region clusters into a single huge group (see the Sprint 4 report,
    "Problemas encontrados") — this version is O(n) per group.
    """
    zones: list[Zone] = []
    group: list[SwingPoint] = []
    group_low: Decimal | None = None
    group_high: Decimal | None = None

    def flush():
        if group:
            zones.append(_build_zone(group, kind, earliest, latest))

    for swing in sorted_swings:
        if not group:
            group.append(swing)
            group_low = group_high = swing.price
            continue

        reference = group_high if kind == ZoneKind.RESISTANCE else group_low
        tolerance = reference * Decimal(str(tolerance_pct))

        if group_low - tolerance <= swing.price <= group_high + tolerance:
            group.append(swing)
            group_high = swing.price  # sorted ascending, so this is always the new max
        else:
            flush()
            group = [swing]
            group_low = group_high = swing.price

    flush()
    return zones


def _build_zone(group: list[SwingPoint], kind: ZoneKind, earliest, latest) -> Zone:
    prices = [s.price for s in group]
    lower_bound = min(prices)
    upper_bound = max(prices)
    price = sum(prices, Decimal(0)) / len(prices)

    first_seen = min(s.confirmation_timestamp for s in group)
    last_seen = max(s.confirmation_timestamp for s in group)

    total_span = (latest - earliest).total_seconds() if earliest and latest and latest > earliest else 0
    recency = (last_seen - earliest).total_seconds() / total_span if total_span > 0 else 1.0
    strength = len(group) * (1 + recency)

    return Zone(
        kind=kind,
        price=price,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        touches=len(group),
        strength=strength,
        first_seen=first_seen,
        last_seen=last_seen,
    )
