from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.schemas import MarketSnapshotOut, StructureHistoryOut, SwingPointOut
from app.data.types import Timeframe
from app.database.session import get_db
from app.market.service import MarketService

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/snapshot", response_model=MarketSnapshotOut)
def get_snapshot(
    symbol: str = Query(...),
    timeframe: str = Query(...),
    timestamp: datetime = Query(...),
    db: Session = Depends(get_db),
) -> MarketSnapshotOut:
    try:
        tf = Timeframe(timeframe)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    snapshot = MarketService(db).get_snapshot(symbol=symbol, timeframe=tf, timestamp=timestamp)
    return MarketSnapshotOut.model_validate(snapshot)


@router.get("/structure", response_model=StructureHistoryOut)
def get_structure(
    symbol: str = Query(...),
    timeframe: str = Query(...),
    start: datetime = Query(...),
    end: datetime = Query(...),
    db: Session = Depends(get_db),
) -> StructureHistoryOut:
    try:
        tf = Timeframe(timeframe)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    analysis = MarketService(db).get_structure_history(symbol=symbol, timeframe=tf, start=start, end=end)
    return StructureHistoryOut(
        symbol=symbol,
        timeframe=tf.value,
        state=analysis.state.value,
        swing_highs=[SwingPointOut.model_validate(s) for s in analysis.confirmed_highs],
        swing_lows=[SwingPointOut.model_validate(s) for s in analysis.confirmed_lows],
        events=analysis.events,
    )
