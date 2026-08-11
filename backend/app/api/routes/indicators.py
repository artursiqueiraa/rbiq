from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas import IndicatorCalculateRequest, IndicatorCalculateResponse, IndicatorSeriesOut
from app.data.types import Timeframe
from app.database.session import get_db
from app.indicators.service import IndicatorService

router = APIRouter(prefix="/api/indicators", tags=["indicators"])


@router.post("/calculate", response_model=IndicatorCalculateResponse)
def calculate(request: IndicatorCalculateRequest, db: Session = Depends(get_db)) -> IndicatorCalculateResponse:
    try:
        timeframe = Timeframe(request.timeframe)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        result = IndicatorService(db).calculate(
            symbol=request.symbol,
            timeframe=timeframe,
            start=request.start,
            end=request.end,
            indicator_specs=[spec.model_dump() for spec in request.indicators],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return IndicatorCalculateResponse(
        symbol=request.symbol,
        timeframe=timeframe.value,
        timestamps=result.timestamps,
        close=result.closes,
        indicators={
            key: IndicatorSeriesOut(parameters=r.parameters, series=r.series)
            for key, r in result.indicators.items()
        },
    )
