from app.market.types import VolatilityRegime

DEFAULT_WINDOW = 100


def normalized_atr_series(atr_values: list[float | None], closes: list[float]) -> list[float | None]:
    """ATR alone can't be compared across assets or price scales — an ATR of
    0.0012 is huge for a currency pair and tiny for an index. Dividing by the
    close price (ATR/close) gives a scale-free, roughly comparable measure,
    per Sprint 4 section 25."""
    return [
        (atr / close) if atr is not None and close else None for atr, close in zip(atr_values, closes)
    ]


def classify_volatility(
    normalized_atr: list[float | None], *, window: int = DEFAULT_WINDOW
) -> tuple[VolatilityRegime, float | None]:
    """Classifies the LATEST normalized-ATR value against its own trailing
    history — not a hardcoded absolute threshold (section 25 explicitly
    forbids that, since assets have different scales). Uses tertiles of the
    trailing `window` values: bottom third -> LOW, top third -> HIGH, middle
    third -> NORMAL. Needs at least 2 historical values to rank against;
    otherwise there's nothing to compare, so the result is UNKNOWN.
    """
    valid_indices = [i for i, v in enumerate(normalized_atr) if v is not None]
    if not valid_indices:
        return VolatilityRegime.UNKNOWN, None

    latest_index = valid_indices[-1]
    latest_value = normalized_atr[latest_index]

    trailing_indices = valid_indices[-window:]
    trailing = [normalized_atr[i] for i in trailing_indices]

    if len(trailing) < 2:
        return VolatilityRegime.UNKNOWN, latest_value

    rank = sum(1 for v in trailing if v <= latest_value) / len(trailing)

    if rank <= 1 / 3:
        return VolatilityRegime.LOW, latest_value
    if rank >= 2 / 3:
        return VolatilityRegime.HIGH, latest_value
    return VolatilityRegime.NORMAL, latest_value
