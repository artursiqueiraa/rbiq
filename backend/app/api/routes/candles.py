from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.schemas import CandleOut, DataQualityOut
from app.database.session import get_db
from app.repositories.candle_repository import CandleRepository

router = APIRouter(prefix="/api/candles", tags=["candles"])

EARLIEST_DEFAULT = datetime(1970, 1, 1, tzinfo=timezone.utc)
LATEST_DEFAULT = datetime(2100, 1, 1, tzinfo=timezone.utc)


@router.get("/quality", response_model=DataQualityOut)
def get_quality(
    symbol: str = Query(...),
    timeframe: str = Query(...),
    db: Session = Depends(get_db),
) -> DataQualityOut:
    report = CandleRepository(db).get_quality(symbol, timeframe)
    return DataQualityOut(**report.__dict__)


@router.get("", response_model=list[CandleOut])
def list_candles(
    symbol: str = Query(...),
    timeframe: str = Query(...),
    start: datetime = Query(default=EARLIEST_DEFAULT),
    end: datetime = Query(default=LATEST_DEFAULT),
    db: Session = Depends(get_db),
) -> list[CandleOut]:
    rows = CandleRepository(db).get(symbol, timeframe, start, end)
    return [CandleOut.model_validate(row) for row in rows]


@router.get("/{symbol}", response_model=list[CandleOut])
def list_candles_by_symbol(
    symbol: str,
    timeframe: str = Query(...),
    start: datetime = Query(default=EARLIEST_DEFAULT),
    end: datetime = Query(default=LATEST_DEFAULT),
    db: Session = Depends(get_db),
) -> list[CandleOut]:
    rows = CandleRepository(db).get(symbol, timeframe, start, end)
    return [CandleOut.model_validate(row) for row in rows]
