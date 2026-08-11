import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.data.providers.csv_provider import CSVProvider
from app.data.quality import DataQualityReport, compute_quality_report
from app.data.types import Candle, DataSource, Timeframe
from app.data.validation import validate_candles
from app.repositories.candle_repository import CandleRepository
from app.repositories.import_repository import ImportRepository

MAX_ERROR_SAMPLES = 10


@dataclass(frozen=True)
class IngestionResult:
    import_id: int
    status: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    duplicates: int
    inserted: int
    quality: DataQualityReport


class DataIngestionService:
    """Orchestrates provider -> normalizer -> validator -> repository. This is the
    only place that is allowed to know all four stages exist; routes and the CLI
    only ever call `ingest_csv`."""

    def __init__(self, session: Session):
        self.session = session
        self.candles = CandleRepository(session)
        self.imports = ImportRepository(session)

    def ingest_csv(
        self,
        *,
        file_path: str | Path,
        symbol: str,
        timeframe: Timeframe,
        column_mapping: dict[str, str] | None = None,
    ) -> IngestionResult:
        file_path = Path(file_path)
        started_at = datetime.now(timezone.utc)

        import_record = self.imports.create(
            provider="csv",
            source_file=str(file_path),
            symbol=symbol,
            timeframe=timeframe,
            started_at=started_at,
        )
        logger.info("IMPORT_STARTED | file={} | symbol={} | timeframe={}", file_path, symbol, timeframe.value)

        try:
            provider = CSVProvider(file_path, column_mapping=column_mapping)
            normalization = provider.normalize(symbol, timeframe, source=DataSource.CSV)
        except (FileNotFoundError, OSError) as exc:
            self.imports.complete(
                import_record.id,
                finished_at=datetime.now(timezone.utc),
                status="FAILED",
                total_rows=0,
                valid_rows=0,
                invalid_rows=0,
                duplicates=0,
                gaps=0,
                errors=json.dumps([str(exc)]),
            )
            logger.error("IMPORT_FAILED | file={} | reason={}", file_path, exc)
            raise

        validation_results = validate_candles(normalization.candles)
        valid_candles: list[Candle] = [r.candle for r in validation_results if r.is_valid]

        total_rows = len(normalization.candles) + len(normalization.errors)
        invalid_rows = total_rows - len(valid_candles)

        invalid_results = [r for r in validation_results if not r.is_valid]
        for result in invalid_results[:MAX_ERROR_SAMPLES]:
            logger.warning(
                "CANDLE_INVALID | symbol={} | timestamp={} | issues={}",
                symbol,
                result.candle.timestamp,
                [i.value for i in result.issues],
            )
        if len(invalid_results) > MAX_ERROR_SAMPLES:
            logger.warning(
                "CANDLE_INVALID | symbol={} | ...and {} more invalid candles (not logged individually)",
                symbol,
                len(invalid_results) - MAX_ERROR_SAMPLES,
            )

        inserted = self.candles.bulk_insert(valid_candles)
        duplicates = len(valid_candles) - inserted

        quality = compute_quality_report(
            [c.timestamp for c in valid_candles],
            symbol=symbol,
            timeframe=timeframe,
            total_candles=total_rows,
            valid_candles=len(valid_candles),
            invalid_candles=invalid_rows,
            duplicates=duplicates,
            out_of_order=normalization.out_of_order_count,
        )

        if quality.gaps:
            logger.warning(
                "DATA_GAP | symbol={} | timeframe={} | gaps={} | first={} | last={}",
                symbol,
                timeframe.value,
                quality.gaps,
                quality.first_gap,
                quality.last_gap,
            )
        if duplicates:
            logger.info("DUPLICATE_CANDLE | symbol={} | count={}", symbol, duplicates)

        if total_rows == 0:
            status = "FAILED"
        elif invalid_rows == 0:
            status = "COMPLETED"
        elif valid_candles:
            status = "PARTIAL"
        else:
            status = "FAILED"

        error_samples = [e.reason for e in normalization.errors[:MAX_ERROR_SAMPLES]]

        self.imports.complete(
            import_record.id,
            finished_at=datetime.now(timezone.utc),
            status=status,
            total_rows=total_rows,
            valid_rows=len(valid_candles),
            invalid_rows=invalid_rows,
            duplicates=duplicates,
            gaps=quality.gaps,
            errors=json.dumps(error_samples) if error_samples else None,
        )

        logger.info(
            "IMPORT_COMPLETED | file={} | status={} | total={} | valid={} | inserted={} | duplicates={}",
            file_path,
            status,
            total_rows,
            len(valid_candles),
            inserted,
            duplicates,
        )

        return IngestionResult(
            import_id=import_record.id,
            status=status,
            total_rows=total_rows,
            valid_rows=len(valid_candles),
            invalid_rows=invalid_rows,
            duplicates=duplicates,
            inserted=inserted,
            quality=quality,
        )
