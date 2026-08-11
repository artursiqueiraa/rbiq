from fastapi.testclient import TestClient

from app.main import app
from tests.strategies.conftest import STRONG_BULLISH_TREND
from tests.strategies.integration.conftest import TEST_SYMBOL_PREFIX, seed_candles

SYMBOL = f"{TEST_SYMBOL_PREFIX}STRATEGY_API"
client = TestClient(app)


def test_evaluate_endpoint_returns_a_signal(db_session):
    candles = seed_candles(db_session, SYMBOL, STRONG_BULLISH_TREND)

    response = client.post(
        "/api/strategies/evaluate",
        json={
            "strategy": "trend_following",
            "symbol": SYMBOL,
            "timeframe": "M1",
            "timestamp": candles[-1].timestamp.isoformat(),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["strategy"] == "trend_following"
    assert body["signal"]["direction"] == "CALL"
    assert "market_direction_bullish" in body["triggered_conditions"]


def test_evaluate_all_endpoint_returns_all_six(db_session):
    candles = seed_candles(db_session, SYMBOL, STRONG_BULLISH_TREND)

    response = client.post(
        "/api/strategies/evaluate-all",
        json={"symbol": SYMBOL, "timeframe": "M1", "timestamp": candles[-1].timestamp.isoformat()},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "trend_following",
        "pullback",
        "breakout",
        "mean_reversion",
        "price_action",
        "divergence",
    }
    assert body["trend_following"]["signal"]["direction"] == "CALL"
    assert body["breakout"]["signal"] is None


def test_evaluate_endpoint_rejects_unknown_strategy(db_session):
    candles = seed_candles(db_session, SYMBOL, STRONG_BULLISH_TREND[:10])
    response = client.post(
        "/api/strategies/evaluate",
        json={
            "strategy": "not_a_real_strategy",
            "symbol": SYMBOL,
            "timeframe": "M1",
            "timestamp": candles[-1].timestamp.isoformat(),
        },
    )
    assert response.status_code == 400


def test_evaluate_endpoint_rejects_invalid_timeframe():
    response = client.post(
        "/api/strategies/evaluate",
        json={"strategy": "trend_following", "symbol": SYMBOL, "timeframe": "M2", "timestamp": "2026-01-01T00:00:00Z"},
    )
    assert response.status_code == 400


def test_evaluate_endpoint_rejects_invalid_strategy_parameters(db_session):
    candles = seed_candles(db_session, SYMBOL, STRONG_BULLISH_TREND[:10])
    response = client.post(
        "/api/strategies/evaluate",
        json={
            "strategy": "trend_following",
            "symbol": SYMBOL,
            "timeframe": "M1",
            "timestamp": candles[-1].timestamp.isoformat(),
            "parameters": {"fast_ema": -5},
        },
    )
    assert response.status_code == 400
