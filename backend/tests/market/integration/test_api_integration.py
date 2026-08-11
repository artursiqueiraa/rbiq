from fastapi.testclient import TestClient

from app.main import app
from tests.market.conftest import BULLISH_CLOSES
from tests.market.integration.conftest import BASE_TS, TEST_SYMBOL_PREFIX, seed_candles

SYMBOL = f"{TEST_SYMBOL_PREFIX}MARKET_API"
client = TestClient(app)


def test_snapshot_endpoint_returns_bullish_structure(db_session):
    candles = seed_candles(db_session, SYMBOL, BULLISH_CLOSES)

    response = client.get(
        "/api/market/snapshot",
        params={"symbol": SYMBOL, "timeframe": "M1", "timestamp": candles[-1].timestamp.isoformat()},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == SYMBOL
    assert body["structure_state"] == "BULLISH"
    assert body["direction"] == "BULLISH"
    assert body["latest_swing_high"] is not None
    assert body["latest_swing_low"] is not None
    assert "confirmation_timestamp" in body["latest_swing_high"]


def test_structure_endpoint_returns_swing_history(db_session):
    candles = seed_candles(db_session, SYMBOL, BULLISH_CLOSES)

    response = client.get(
        "/api/market/structure",
        params={
            "symbol": SYMBOL,
            "timeframe": "M1",
            "start": BASE_TS.isoformat(),
            "end": candles[-1].timestamp.isoformat(),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "BULLISH"
    assert len(body["swing_highs"]) == 2
    assert len(body["swing_lows"]) == 2
    assert len(body["events"]) > 0


def test_snapshot_endpoint_rejects_invalid_timeframe():
    response = client.get(
        "/api/market/snapshot",
        params={"symbol": SYMBOL, "timeframe": "M2", "timestamp": BASE_TS.isoformat()},
    )
    assert response.status_code == 400


def test_snapshot_endpoint_empty_symbol_returns_unknown(db_session):
    response = client.get(
        "/api/market/snapshot",
        params={"symbol": f"{TEST_SYMBOL_PREFIX}NOPE", "timeframe": "M1", "timestamp": BASE_TS.isoformat()},
    )
    assert response.status_code == 200
    assert response.json()["structure_state"] == "UNKNOWN"
