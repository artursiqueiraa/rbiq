from abc import ABC, abstractmethod
from datetime import datetime

from app.data.types import Candle, Timeframe


class DataProvider(ABC):
    """Abstraction over any source of market candles.

    Concrete implementations (CSVProvider, ParquetProvider, IQOptionProvider, ...)
    are added in later sprints. Nothing here talks to an external service.
    """

    @abstractmethod
    async def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        raise NotImplementedError
