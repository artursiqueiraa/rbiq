from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.data.types import Timeframe
from app.indicators.registry import IndicatorRegistry, calculate_indicators
from app.indicators.types import IndicatorResult
from app.repositories.candle_repository import CandleRepository


@dataclass(frozen=True)
class IndicatorCalculation:
    timestamps: list[datetime]
    closes: list[float]
    indicators: dict[str, IndicatorResult]


class IndicatorService:
    """The only thing between the API/CLI and the Indicators Engine: fetches
    candles, builds the requested indicators from the registry, runs them, and
    hands back a response-shaped result. No formula lives here — this is
    plumbing, not math."""

    def __init__(self, session: Session):
        self.candles = CandleRepository(session)

    def calculate(
        self,
        *,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
        indicator_specs: list[dict],
    ) -> IndicatorCalculation:
        candles = self.candles.get_domain(symbol, timeframe, start, end)

        indicators = [
            IndicatorRegistry.create(spec["name"], **spec.get("parameters", {})) for spec in indicator_specs
        ]
        results = calculate_indicators(candles, indicators)

        return IndicatorCalculation(
            timestamps=[c.timestamp for c in candles],
            closes=[float(c.close) for c in candles],
            indicators=results,
        )
