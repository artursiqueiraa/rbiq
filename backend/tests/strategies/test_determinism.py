import pytest

from app.strategies.breakout import Breakout
from app.strategies.divergence import Divergence
from app.strategies.mean_reversion import MeanReversion
from app.strategies.price_action import PriceAction
from app.strategies.pullback import Pullback
from app.strategies.trend_following import TrendFollowing
from tests.strategies.conftest import STRONG_BULLISH_TREND, build_context, make_candles

FACTORIES = [
    lambda: TrendFollowing(),
    lambda: Pullback(pullback_tolerance_pct=0.02),
    lambda: Breakout(confirmation_candles=3),
    lambda: MeanReversion(),
    lambda: PriceAction(),
    lambda: Divergence(),
]


@pytest.mark.parametrize("factory", FACTORIES, ids=[f().name for f in FACTORIES])
def test_evaluation_is_deterministic(factory):
    """Section 59: evaluate(context) called twice must agree on everything
    except the wall-clock evaluated_at stamp (see StrategyEvaluation's
    docstring for why that field is deliberately excluded)."""
    candles = make_candles(STRONG_BULLISH_TREND)
    strategy_a = factory()
    strategy_b = factory()
    ctx_a = build_context(candles, strategy_a)
    ctx_b = build_context(candles, strategy_b)

    result_a = strategy_a.evaluate(ctx_a)
    result_b = strategy_b.evaluate(ctx_b)

    assert result_a.triggered_conditions == result_b.triggered_conditions
    assert result_a.failed_conditions == result_b.failed_conditions
    assert result_a.diagnostics == result_b.diagnostics
    assert result_a.signal == result_b.signal  # includes the deterministic id


@pytest.mark.parametrize("factory", FACTORIES, ids=[f().name for f in FACTORIES])
def test_candles_are_not_mutated(factory):
    candles = make_candles(STRONG_BULLISH_TREND)
    candles_before = list(candles)

    strategy = factory()
    ctx = build_context(candles, strategy)
    strategy.prepare(ctx)
    strategy.evaluate(ctx)

    assert candles == candles_before
    assert all(c1 is c2 for c1, c2 in zip(candles, candles_before))
