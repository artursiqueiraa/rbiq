from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.data.types import Timeframe
from app.market.types import (
    MarketDirection,
    MarketRegime,
    MarketSnapshot,
    StructureState,
    VolatilityRegime,
    Zone,
    ZoneKind,
)
from app.strategies.context import StrategyContext
from app.strategies.pullback_zones import PullbackZones
from app.strategies.types import SignalDirection
from tests.strategies.conftest import STRONG_BULLISH_TREND, build_context, make_candles

BASE_TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _mk_zone(kind: ZoneKind, price: float, strength: float) -> Zone:
    return Zone(
        kind=kind,
        price=Decimal(str(price)),
        lower_bound=Decimal(str(price - 0.5)),
        upper_bound=Decimal(str(price + 0.5)),
        touches=3,
        strength=strength,
        first_seen=BASE_TS,
        last_seen=BASE_TS + timedelta(minutes=5),
    )


def _mk_context(
    closes: list[float],
    *,
    direction: MarketDirection = MarketDirection.BULLISH,
    structure: StructureState = StructureState.BULLISH,
    regime: str = "TRENDING_BULLISH",
    volatility: VolatilityRegime = VolatilityRegime.NORMAL,
    supports: list[Zone] | None = None,
    resistances: list[Zone] | None = None,
) -> StrategyContext:
    """Constrói um StrategyContext com um MarketSnapshot MONTADO À MÃO (não
    via build_snapshot real) — dá controle direto sobre zonas/volatilidade,
    que são difíceis de engenheirar de forma confiável a partir de só uma
    série de preços (dependem de detecção de swing + clustering real)."""
    candles = make_candles(closes)
    snapshot = MarketSnapshot(
        symbol="TEST",
        timeframe=Timeframe.M1,
        timestamp=candles[-1].timestamp,
        direction=direction,
        structure_state=structure,
        regime=MarketRegime(regime),
        volatility=volatility,
        volatility_value=1.0,
        trend_strength=0.5,
        latest_swing_high=None,
        latest_swing_low=None,
        supports=supports or [],
        resistances=resistances or [],
        structure_events=[],
    )
    return StrategyContext(
        symbol="TEST",
        timeframe=Timeframe.M1,
        timestamp=candles[-1].timestamp,
        market_snapshot=snapshot,
        candles=candles,
        indicators={},
    )


# candles: correção descendo até ~95, depois retoma subindo, fechando > close
# anterior e > mínima da correção. lookback_candles=5 nos testes abaixo (não
# o default 10) para casar com o tamanho pequeno destas listas — min_len =
# lookback + 2.
BULLISH_PULLBACK_CLOSES = [100, 98, 96, 95, 96, 98, 101]
BEARISH_PULLBACK_CLOSES = [100, 102, 104, 105, 104, 102, 99]
LOOKBACK = 5


def test_call_fires_when_pullback_touches_strong_support_zone():
    strong_support = _mk_zone(ZoneKind.SUPPORT, price=95.0, strength=2.0)
    ctx = _mk_context(BULLISH_PULLBACK_CLOSES, supports=[strong_support])
    strategy = PullbackZones(lookback_candles=LOOKBACK, zone_tolerance_pct=0.05, min_zone_strength=1.5)

    evaluation = strategy.evaluate(ctx)

    assert "pullback_near_strong_support" in evaluation.triggered_conditions
    assert "resumption_confirmed" in evaluation.triggered_conditions
    assert evaluation.signal is not None
    assert evaluation.signal.direction == SignalDirection.CALL


def test_put_fires_when_pullback_touches_strong_resistance_zone():
    strong_resistance = _mk_zone(ZoneKind.RESISTANCE, price=105.0, strength=2.0)
    ctx = _mk_context(
        BEARISH_PULLBACK_CLOSES,
        direction=MarketDirection.BEARISH,
        structure=StructureState.BEARISH,
        regime="TRENDING_BEARISH",
        resistances=[strong_resistance],
    )
    strategy = PullbackZones(lookback_candles=LOOKBACK, zone_tolerance_pct=0.05, min_zone_strength=1.5)

    evaluation = strategy.evaluate(ctx)

    assert "pullback_near_strong_resistance" in evaluation.triggered_conditions
    assert evaluation.signal is not None
    assert evaluation.signal.direction == SignalDirection.PUT


def test_weak_zone_does_not_count_as_strong():
    weak_support = _mk_zone(ZoneKind.SUPPORT, price=95.0, strength=0.5)  # abaixo do min_zone_strength
    ctx = _mk_context(BULLISH_PULLBACK_CLOSES, supports=[weak_support])
    strategy = PullbackZones(lookback_candles=LOOKBACK, zone_tolerance_pct=0.05, min_zone_strength=1.5)

    evaluation = strategy.evaluate(ctx)

    assert "pullback_near_strong_support" in evaluation.failed_conditions


def test_zone_far_from_price_does_not_count_even_if_strong():
    far_support = _mk_zone(ZoneKind.SUPPORT, price=50.0, strength=5.0)  # longe do preço da correção
    ctx = _mk_context(BULLISH_PULLBACK_CLOSES, supports=[far_support])
    strategy = PullbackZones(lookback_candles=LOOKBACK, zone_tolerance_pct=0.02, min_zone_strength=1.5)

    evaluation = strategy.evaluate(ctx)

    assert "pullback_near_strong_support" in evaluation.failed_conditions


def test_low_volatility_blocks_entry_when_required():
    strong_support = _mk_zone(ZoneKind.SUPPORT, price=95.0, strength=2.0)
    ctx = _mk_context(BULLISH_PULLBACK_CLOSES, volatility=VolatilityRegime.LOW, supports=[strong_support])
    strategy = PullbackZones(
        lookback_candles=LOOKBACK, zone_tolerance_pct=0.05, min_zone_strength=1.5, require_elevated_volatility=True
    )

    evaluation = strategy.evaluate(ctx)

    assert "volatility_acceptable" in evaluation.failed_conditions


def test_low_volatility_allowed_when_not_required():
    strong_support = _mk_zone(ZoneKind.SUPPORT, price=95.0, strength=2.0)
    ctx = _mk_context(BULLISH_PULLBACK_CLOSES, volatility=VolatilityRegime.LOW, supports=[strong_support])
    strategy = PullbackZones(
        lookback_candles=LOOKBACK, zone_tolerance_pct=0.05, min_zone_strength=1.5, require_elevated_volatility=False
    )

    evaluation = strategy.evaluate(ctx)

    assert "volatility_acceptable" in evaluation.triggered_conditions


def test_incompatible_regime_fails_that_condition():
    strong_support = _mk_zone(ZoneKind.SUPPORT, price=95.0, strength=2.0)
    ctx = _mk_context(BULLISH_PULLBACK_CLOSES, regime="RANGING", supports=[strong_support])
    strategy = PullbackZones(lookback_candles=LOOKBACK, zone_tolerance_pct=0.05, min_zone_strength=1.5)

    evaluation = strategy.evaluate(ctx)

    assert "regime_compatible" in evaluation.failed_conditions


def test_insufficient_data_returns_no_signal():
    ctx = _mk_context([10, 11, 12])
    strategy = PullbackZones()
    evaluation = strategy.evaluate(ctx)
    assert evaluation.signal is None
    assert any("insufficient_data" in d for d in evaluation.diagnostics)


def test_required_indicators_is_empty():
    # zonas e volatilidade já vêm prontas no MarketSnapshot — não precisa
    # de nenhum indicador do Indicators Engine.
    assert PullbackZones().required_indicators() == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"lookback_candles": 0},
        {"zone_tolerance_pct": -0.1},
        {"zone_tolerance_pct": 1.5},
        {"min_zone_strength": -1.0},
    ],
)
def test_validate_parameters_rejects_invalid_values(kwargs):
    with pytest.raises(ValueError):
        PullbackZones(**kwargs)


def test_determinism_same_context_same_result():
    strong_support = _mk_zone(ZoneKind.SUPPORT, price=95.0, strength=2.0)
    ctx = _mk_context(BULLISH_PULLBACK_CLOSES, supports=[strong_support])
    strategy = PullbackZones(lookback_candles=LOOKBACK, zone_tolerance_pct=0.05, min_zone_strength=1.5)

    eval_a = strategy.evaluate(ctx)
    eval_b = strategy.evaluate(ctx)

    assert eval_a.signal.direction == eval_b.signal.direction
    assert eval_a.signal.confidence == eval_b.signal.confidence
    assert eval_a.signal.conditions == eval_b.signal.conditions
    assert eval_a.signal.id == eval_b.signal.id  # id é determinístico, não uuid4


def test_runs_against_the_real_market_engine_pipeline_without_crashing():
    # Smoke test com build_snapshot de verdade (não a MarketSnapshot
    # montada à mão dos testes acima) — prova que a estratégia não quebra
    # contra zonas/volatilidade reais, mesmo sem controlar se ela dispara.
    candles = make_candles(STRONG_BULLISH_TREND)
    strategy = PullbackZones()
    ctx = build_context(candles, strategy)
    evaluation = strategy.evaluate(ctx)
    assert evaluation is not None  # não lança, sempre devolve uma StrategyEvaluation válida
