from app.market.types import MarketDirection, MarketRegime, StructureState, VolatilityRegime

_DIRECTION_FROM_STATE = {
    StructureState.BULLISH: MarketDirection.BULLISH,
    StructureState.BEARISH: MarketDirection.BEARISH,
    StructureState.RANGE: MarketDirection.NEUTRAL,
    StructureState.TRANSITION: MarketDirection.NEUTRAL,
    StructureState.UNKNOWN: MarketDirection.UNKNOWN,
}


def direction_from_structure(state: StructureState) -> MarketDirection:
    """Direction is read straight off the already-computed structure state
    rather than re-derived independently — one causal, tested computation
    (structure_engine.analyze_structure) feeding two output fields, instead of
    two places that could disagree."""
    return _DIRECTION_FROM_STATE[state]


def classify_regime(state: StructureState, volatility: VolatilityRegime) -> MarketRegime:
    """direction/regime/volatility are separate MarketSnapshot fields (section
    21), but `regime` still needs one concrete value. The mapping:

    BULLISH     -> TRENDING_BULLISH
    BEARISH     -> TRENDING_BEARISH
    TRANSITION  -> TRANSITION
    RANGE       -> RANGING, unless volatility is HIGH or LOW, in which case
                   that's the more informative label (a choppy range and a
                   quiet range are meaningfully different states, and
                   `volatility` is reported separately anyway so this doesn't
                   lose information — it just picks the more useful single
                   `regime` value when structure alone says "nothing directional
                   is happening").
    UNKNOWN     -> UNKNOWN
    """
    if state == StructureState.BULLISH:
        return MarketRegime.TRENDING_BULLISH
    if state == StructureState.BEARISH:
        return MarketRegime.TRENDING_BEARISH
    if state == StructureState.TRANSITION:
        return MarketRegime.TRANSITION
    if state == StructureState.RANGE:
        if volatility == VolatilityRegime.HIGH:
            return MarketRegime.HIGH_VOLATILITY
        if volatility == VolatilityRegime.LOW:
            return MarketRegime.LOW_VOLATILITY
        return MarketRegime.RANGING
    return MarketRegime.UNKNOWN
