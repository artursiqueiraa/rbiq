from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.schemas import ImportJobOut, ImportRequest, ImportResultOut
from app.data.ingestion import DataIngestionService
from app.data.types import Timeframe
from app.database.session import get_db
from app.repositories.import_repository import ImportRepository

router = APIRouter(prefix="/api/data", tags=["data"])

# backend/app/api/routes/data.py -> project root is four levels up
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_ALLOWED_ROOT = (_PROJECT_ROOT / "data" / "raw").resolve()


def _resolve_safe_path(raw_path: str) -> Path:
    """Only files inside data/raw/ can be imported through the API — this is the
    only thing standing between a client-supplied string and the filesystem, so a
    naive `../../etc/passwd` style traversal must be rejected outright."""
    candidate = (_PROJECT_ROOT / raw_path).resolve()
    if _ALLOWED_ROOT not in candidate.parents and candidate != _ALLOWED_ROOT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file must be located inside data/raw/",
        )
    if not candidate.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file not found")
    return candidate


@router.post("/import", response_model=ImportResultOut)
def import_dataset(request: ImportRequest, db: Session = Depends(get_db)) -> ImportResultOut:
    if request.provider != "csv":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unsupported provider: {request.provider!r} (only 'csv' is implemented)",
        )

    try:
        timeframe = Timeframe(request.timeframe)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    file_path = _resolve_safe_path(request.file)

    service = DataIngestionService(db)
    result = service.ingest_csv(
        file_path=file_path,
        symbol=request.symbol,
        timeframe=timeframe,
        column_mapping=request.column_mapping,
    )

    return ImportResultOut(
        import_id=result.import_id,
        status=result.status,
        total_rows=result.total_rows,
        valid_rows=result.valid_rows,
        invalid_rows=result.invalid_rows,
        duplicates=result.duplicates,
        inserted=result.inserted,
        gaps=result.quality.gaps,
    )


@router.get("/imports", response_model=list[ImportJobOut])
def list_imports(limit: int = Query(default=50, le=200), db: Session = Depends(get_db)) -> list[ImportJobOut]:
    records = ImportRepository(db).list_recent(limit=limit)
    return [ImportJobOut.model_validate(record) for record in records]
