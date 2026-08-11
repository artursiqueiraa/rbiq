from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.types import Timeframe
from app.database.models import DataImportModel


class ImportRepository:
    """Persistence for the data_imports history table."""

    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        *,
        provider: str,
        source_file: str,
        symbol: str,
        timeframe: Timeframe,
        started_at: datetime,
    ) -> DataImportModel:
        record = DataImportModel(
            provider=provider,
            source_file=source_file,
            symbol=symbol,
            timeframe=timeframe.value,
            started_at=started_at,
            status="RUNNING",
            total_rows=0,
            valid_rows=0,
            invalid_rows=0,
            duplicates=0,
            gaps=0,
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def complete(
        self,
        import_id: int,
        *,
        finished_at: datetime,
        status: str,
        total_rows: int,
        valid_rows: int,
        invalid_rows: int,
        duplicates: int,
        gaps: int,
        errors: str | None = None,
    ) -> DataImportModel:
        record = self.session.get(DataImportModel, import_id)
        if record is None:
            raise ValueError(f"import {import_id} not found")

        record.finished_at = finished_at
        record.status = status
        record.total_rows = total_rows
        record.valid_rows = valid_rows
        record.invalid_rows = invalid_rows
        record.duplicates = duplicates
        record.gaps = gaps
        record.errors = errors

        self.session.commit()
        self.session.refresh(record)
        return record

    def list_recent(self, limit: int = 50) -> list[DataImportModel]:
        stmt = select(DataImportModel).order_by(DataImportModel.started_at.desc()).limit(limit)
        return list(self.session.execute(stmt).scalars().all())
