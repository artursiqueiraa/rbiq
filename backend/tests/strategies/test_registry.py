import pytest

from app.strategies.breakout import Breakout
from app.strategies.divergence import Divergence
from app.strategies.mean_reversion import MeanReversion
from app.strategies.price_action import PriceAction
from app.strategies.pullback import Pullback
from app.strategies.pullback_zones import PullbackZones
from app.strategies.registry import StrategyRegistry
from app.strategies.trend_following import TrendFollowing


@pytest.mark.parametrize(
    "name,cls",
    [
        ("trend_following", TrendFollowing),
        ("pullback", Pullback),
        ("pullback_zones", PullbackZones),
        ("breakout", Breakout),
        ("mean_reversion", MeanReversion),
        ("price_action", PriceAction),
        ("divergence", Divergence),
    ],
)
def test_get_returns_the_right_class(name, cls):
    assert StrategyRegistry.get(name) is cls


def test_get_is_case_insensitive():
    assert StrategyRegistry.get("TREND_FOLLOWING") is TrendFollowing


def test_unknown_strategy_raises_value_error():
    with pytest.raises(ValueError):
        StrategyRegistry.get("not_a_real_strategy")


def test_create_builds_a_configured_instance():
    strategy = StrategyRegistry.create("trend_following", fast_ema=10)
    assert isinstance(strategy, TrendFollowing)
    assert strategy.parameters["fast_ema"] == 10


def test_names_lists_all_seven():
    assert StrategyRegistry.names() == [
        "breakout",
        "divergence",
        "mean_reversion",
        "price_action",
        "pullback",
        "pullback_zones",
        "trend_following",
    ]
