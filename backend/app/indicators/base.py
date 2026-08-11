from abc import ABC, abstractmethod
from typing import ClassVar

from app.data.types import Candle
from app.indicators.types import IndicatorResult


class Indicator(ABC):
    """An indicator turns a causally-ordered list of candles into an
    IndicatorResult. It reads prices; it never decides direction, never knows
    about CALL/PUT, strategies, payout, or execution — that boundary is what
    keeps this engine reusable by anything built on top of it later.

    Subclasses validate their own parameters in __init__ (raise ValueError for
    anything invalid) and must not mutate the `candles` list passed to
    `calculate`.
    """

    name: ClassVar[str]

    @abstractmethod
    def calculate(self, candles: list[Candle]) -> IndicatorResult:
        raise NotImplementedError
