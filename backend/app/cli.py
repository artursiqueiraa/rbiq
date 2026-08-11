import argparse
import sys

from app.data.ingestion import DataIngestionService
from app.data.types import Timeframe
from app.database.session import SessionLocal
from app.repositories.candle_repository import CandleRepository


def cmd_import_csv(args: argparse.Namespace) -> None:
    timeframe = Timeframe(args.timeframe)

    with SessionLocal() as session:
        service = DataIngestionService(session)
        result = service.ingest_csv(file_path=args.file, symbol=args.symbol, timeframe=timeframe)

    print(f"Import {result.status}")
    print(f"  import_id:    {result.import_id}")
    print(f"  total_rows:   {result.total_rows}")
    print(f"  valid_rows:   {result.valid_rows}")
    print(f"  invalid_rows: {result.invalid_rows}")
    print(f"  duplicates:   {result.duplicates}")
    print(f"  inserted:     {result.inserted}")
    print(f"  gaps:         {result.quality.gaps}")

    if result.status == "FAILED":
        sys.exit(1)


def cmd_validate(args: argparse.Namespace) -> None:
    timeframe = Timeframe(args.timeframe)

    with SessionLocal() as session:
        report = CandleRepository(session).get_quality(args.symbol, timeframe)

    print("Data Quality Report")
    print()
    print(f"Candles:       {report.total_candles}")
    print(f"Valid:         {report.valid_candles}")
    print(f"Invalid:       {report.invalid_candles}")
    print(f"Duplicates:    {report.duplicates}")
    print(f"Gaps:          {report.gaps}")
    print(f"Out-of-order:  {report.out_of_order}")
    print()
    print(f"Quality Score: {report.quality_score}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_parser = subparsers.add_parser("import-csv", help="Import candles from a CSV file")
    import_parser.add_argument("--file", required=True, help="Path relative to the project root, e.g. data/raw/EURUSD_M1.csv")
    import_parser.add_argument("--symbol", required=True)
    import_parser.add_argument("--timeframe", required=True, choices=[t.value for t in Timeframe])
    import_parser.set_defaults(func=cmd_import_csv)

    validate_parser = subparsers.add_parser("validate", help="Print a data quality report for stored candles")
    validate_parser.add_argument("--symbol", required=True)
    validate_parser.add_argument("--timeframe", required=True, choices=[t.value for t in Timeframe])
    validate_parser.set_defaults(func=cmd_validate)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
