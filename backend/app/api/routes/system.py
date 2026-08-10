from fastapi import APIRouter, Depends, Response, status

from app.core.config import Settings, get_settings
from app.database.session import check_database_connection

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "status": "healthy",
        "service": "iqo-strategy-lab",
        "version": settings.app_version,
    }


@router.get("/health/database")
def health_database(response: Response) -> dict:
    if check_database_connection():
        return {"status": "healthy", "database": "postgresql"}

    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "unhealthy", "database": "postgresql"}


@router.get("/health/full")
def health_full(response: Response) -> dict:
    database_ok = check_database_connection()

    if not database_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "healthy" if database_ok else "unhealthy",
        "api": "healthy",
        "database": "healthy" if database_ok else "unhealthy",
    }
