from dataclasses import dataclass, field

from app.data.types import Candle
from app.market.structure.trend import SwingComparison, classify_state, compare_swing
from app.market.types import StructureEvent, StructureEventType, StructureState, SwingPoint, SwingType

_COMPARISON_EVENTS = {
    (SwingType.HIGH, SwingComparison.HIGHER): StructureEventType.HIGHER_HIGH,
    (SwingType.HIGH, SwingComparison.LOWER): StructureEventType.LOWER_HIGH,
    (SwingType.LOW, SwingComparison.HIGHER): StructureEventType.HIGHER_LOW,
    (SwingType.LOW, SwingComparison.LOWER): StructureEventType.LOWER_LOW,
}


@dataclass(frozen=True)
class StructureAnalysis:
    state: StructureState
    events: list[StructureEvent]
    confirmed_highs: list[SwingPoint]
    confirmed_lows: list[SwingPoint]


def analyze_structure(candles: list[Candle], swings: list[SwingPoint]) -> StructureAnalysis:
    """Walks `candles` in chronological order, only ever using swings whose
    `confirmation_timestamp` has been reached by the candle currently being
    processed. This is what makes the whole analysis causal: replaying this
    function over a prefix of `candles` produces exactly the same events (up
    to that prefix) as replaying it over the full list — nothing here can be
    influenced by data whose confirmation lies in the future relative to the
    candle being processed.

    Emits, in causal order:
      SWING_HIGH_CONFIRMED / SWING_LOW_CONFIRMED   — whenever a swing's
          confirmation_timestamp is reached
      HIGHER_HIGH / LOWER_HIGH / HIGHER_LOW / LOWER_LOW — comparing a newly
          confirmed swing to the previous confirmed swing of the same type
          (see trend.compare_swing; EQUAL emits no comparison event)
      STRUCTURE_CHANGE  — whenever classify_state()'s result changes
      STRUCTURE_BREAK    — a close price crosses the structure's own reference
          level: below the latest confirmed higher-low while BULLISH, or above
          the latest confirmed lower-high while BEARISH. Forces the state to
          TRANSITION (the old trend's premise just failed, but a new one isn't
          established yet).
    """
    events: list[StructureEvent] = []
    confirmed_highs: list[SwingPoint] = []
    confirmed_lows: list[SwingPoint] = []
    state = StructureState.UNKNOWN

    swings_by_confirmation = sorted(swings, key=lambda s: s.confirmation_timestamp)
    cursor = 0
    total = len(swings_by_confirmation)

    for candle in candles:
        while cursor < total and swings_by_confirmation[cursor].confirmation_timestamp <= candle.timestamp:
            swing = swings_by_confirmation[cursor]
            cursor += 1

            confirmed_list = confirmed_highs if swing.type == SwingType.HIGH else confirmed_lows
            confirmed_event = (
                StructureEventType.SWING_HIGH_CONFIRMED
                if swing.type == SwingType.HIGH
                else StructureEventType.SWING_LOW_CONFIRMED
            )
            events.append(
                StructureEvent(
                    event_type=confirmed_event,
                    timestamp=swing.timestamp,
                    confirmation_timestamp=swing.confirmation_timestamp,
                    price=swing.price,
                )
            )

            if confirmed_list:
                comparison = compare_swing(swing, confirmed_list[-1])
                comparison_event = _COMPARISON_EVENTS.get((swing.type, comparison))
                if comparison_event is not None:
                    events.append(
                        StructureEvent(
                            event_type=comparison_event,
                            timestamp=swing.timestamp,
                            confirmation_timestamp=swing.confirmation_timestamp,
                            price=swing.price,
                        )
                    )

            confirmed_list.append(swing)

            new_state = classify_state(confirmed_highs, confirmed_lows)
            if new_state != state:
                state = new_state
                events.append(
                    _structure_change_event(swing.confirmation_timestamp, swing.price, state)
                )

        if state == StructureState.BULLISH and confirmed_lows and candle.close < confirmed_lows[-1].price:
            events.append(
                StructureEvent(
                    event_type=StructureEventType.STRUCTURE_BREAK,
                    timestamp=candle.timestamp,
                    confirmation_timestamp=candle.timestamp,
                    price=candle.close,
                    metadata={"broke_below": str(confirmed_lows[-1].price)},
                )
            )
            state = StructureState.TRANSITION
            events.append(_structure_change_event(candle.timestamp, candle.close, state))
        elif state == StructureState.BEARISH and confirmed_highs and candle.close > confirmed_highs[-1].price:
            events.append(
                StructureEvent(
                    event_type=StructureEventType.STRUCTURE_BREAK,
                    timestamp=candle.timestamp,
                    confirmation_timestamp=candle.timestamp,
                    price=candle.close,
                    metadata={"broke_above": str(confirmed_highs[-1].price)},
                )
            )
            state = StructureState.TRANSITION
            events.append(_structure_change_event(candle.timestamp, candle.close, state))

    return StructureAnalysis(state=state, events=events, confirmed_highs=confirmed_highs, confirmed_lows=confirmed_lows)


def _structure_change_event(timestamp, price, new_state: StructureState) -> StructureEvent:
    return StructureEvent(
        event_type=StructureEventType.STRUCTURE_CHANGE,
        timestamp=timestamp,
        confirmation_timestamp=timestamp,
        price=price,
        metadata={"new_state": new_state.value},
    )
