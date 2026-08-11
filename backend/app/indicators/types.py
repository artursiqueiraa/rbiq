from dataclasses import dataclass


@dataclass(frozen=True)
class IndicatorResult:
    """Every indicator returns one of these, regardless of how many series it
    produces internally.

    `series` maps a series name to a list the same length as the input candles.
    Single-series indicators (SMA, EMA, RSI, ATR, CCI) use the key "value".
    Multi-series indicators use their natural component names — MACD uses
    "macd"/"signal"/"histogram", Bollinger uses "middle"/"upper"/"lower",
    Stochastic uses "k"/"d".

    A `None` at index i means "not enough history at this point to produce a
    number" — this project never fabricates a value to fill that gap.
    """

    name: str
    parameters: dict
    series: dict[str, list[float | None]]
