from app.strategies.base import Strategy
from app.strategies.breakout import Breakout
from app.strategies.divergence import Divergence
from app.strategies.mean_reversion import MeanReversion
from app.strategies.price_action import PriceAction
from app.strategies.pullback import Pullback
from app.strategies.pullback_zones import PullbackZones
from app.strategies.trend_following import TrendFollowing

_STRATEGIES: dict[str, type[Strategy]] = {
    cls.name: cls
    for cls in (TrendFollowing, Pullback, PullbackZones, Breakout, MeanReversion, PriceAction, Divergence)
}


class StrategyRegistry:
    """Looks strategies up by name — the API, the CLI, and evaluate_all() all
    go through this instead of an `if name == "trend_following": ...` chain."""

    @staticmethod
    def get(name: str) -> type[Strategy]:
        try:
            return _STRATEGIES[name.lower()]
        except KeyError:
            raise ValueError(f"unknown strategy: {name!r} (known: {sorted(_STRATEGIES)})") from None

    @staticmethod
    def create(name: str, **parameters) -> Strategy:
        return StrategyRegistry.get(name)(**parameters)

    @staticmethod
    def names() -> list[str]:
        return sorted(_STRATEGIES)
