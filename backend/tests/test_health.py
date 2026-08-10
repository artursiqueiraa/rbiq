from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_api_starts_and_health_returns_200():
    response = client.get("/api/system/health")
    assert response.status_code == 200


def test_health_response_shape():
    response = client.get("/api/system/health")
    body = response.json()

    assert body["status"] == "healthy"
    assert body["service"] == "iqo-strategy-lab"
    assert "version" in body


def test_database_health_reports_status_field():
    response = client.get("/api/system/health/database")

    assert response.status_code in (200, 503)
    assert "database" in response.json()
