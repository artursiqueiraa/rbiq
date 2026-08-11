from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas import (
    EvaluateAllRequest,
    StrategyEvaluateRequest,
    StrategyEvaluationOut,
)
from app.data.types import Timeframe
from app.database.session import get_db
from app.strategies.service import StrategyService

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


@router.post("/evaluate", response_model=StrategyEvaluationOut)
def evaluate(request: StrategyEvaluateRequest, db: Session = Depends(get_db)) -> StrategyEvaluationOut:
    try:
        timeframe = Timeframe(request.timeframe)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        result = StrategyService(db).evaluate(
            strategy_name=request.strategy,
            symbol=request.symbol,
            timeframe=timeframe,
            timestamp=request.timestamp,
            parameters=request.parameters,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return StrategyEvaluationOut.model_validate(result)


@router.post("/evaluate-all", response_model=dict[str, StrategyEvaluationOut])
def evaluate_all(request: EvaluateAllRequest, db: Session = Depends(get_db)) -> dict[str, StrategyEvaluationOut]:
    try:
        timeframe = Timeframe(request.timeframe)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    results = StrategyService(db).evaluate_all(symbol=request.symbol, timeframe=timeframe, timestamp=request.timestamp)
    return {name: StrategyEvaluationOut.model_validate(result) for name, result in results.items()}
