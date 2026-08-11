from datetime import timedelta

from fastapi.testclient import TestClient

from app.main import app
from tests.indicators.integration.conftest import BASE_TS, TEST_SYMBOL_PREFIX, seed_candles

SYMBOL = f"{TEST_SYMBOL_PREFIX}IND_API"
client = TestClient(app)


def test_calculate_endpoint_returns_indicator_series(db_session):
    closes = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]
    seed_candles(db_session, SYMBOL, closes)

    response = client.post(
        "/api/indicators/calculate",
        json={
            "symbol": SYMBOL,
            "timeframe": "M1",
            "start": BASE_TS.isoformat(),
            "end": (BASE_TS + timedelta(minutes=len(closes))).isoformat(),
            "indicators": [
                {"name": "EMA", "parameters": {"period": 3}},
                {"name": "MACD", "parameters": {"fast_period": 2, "slow_period": 3, "signal_period": 2}},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == SYMBOL
    assert len(body["timestamps"]) == len(closes)
    assert len(body["close"]) == len(closes)
    assert "EMA_3" in body["indicators"]
    assert "MACD_2_3_2" in body["indicators"]
    assert set(body["indicators"]["MACD_2_3_2"]["series"].keys()) == {"macd", "signal", "histogram"}


def test_calculate_endpoint_rejects_unknown_indicator(db_session):
    seed_candles(db_session, SYMBOL, [10, 11, 12])

    response = client.post(
        "/api/indicators/calculate",
        json={
            "symbol": SYMBOL,
            "timeframe": "M1",
            "start": BASE_TS.isoformat(),
            "end": (BASE_TS + timedelta(minutes=3)).isoformat(),
            "indicators": [{"name": "NOT_REAL_INDICATOR", "parameters": {}}],
        },
    )

    assert response.status_code == 400


def test_calculate_endpoint_rejects_invalid_period():
    response = client.post(
        "/api/indicators/calculate",
        json={
            "symbol": SYMBOL,
            "timeframe": "M1",
            "start": BASE_TS.isoformat(),
            "end": (BASE_TS + timedelta(minutes=3)).isoformat(),
            "indicators": [{"name": "SMA", "parameters": {"period": -1}}],
        },
    )

    assert response.status_code == 400


def test_calculate_endpoint_rejects_invalid_timeframe():
    response = client.post(
        "/api/indicators/calculate",
        json={
            "symbol": SYMBOL,
            "timeframe": "M2",
            "start": BASE_TS.isoformat(),
            "end": (BASE_TS + timedelta(minutes=3)).isoformat(),
            "indicators": [{"name": "SMA", "parameters": {"period": 3}}],
        },
    )

    assert response.status_code == 400
