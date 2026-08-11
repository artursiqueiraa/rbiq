from datetime import datetime, timezone


def to_comparable_utc(ts: datetime) -> datetime:
    """For ordering/filtering only — never for persistence or validation output.

    A naive timestamp is itself a data-quality problem the Validator is meant to
    catch. But comparing a naive and a tz-aware datetime raises TypeError, and one
    bad row should never crash sorting or range-filtering for an entire batch, so
    callers that only need relative ordering treat naive values as if they were UTC.
    """
    return ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)
