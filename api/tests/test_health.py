from fastapi.testclient import TestClient

from api.main import app


def test_health_returns_200():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_status_ok():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.json() == {"status": "ok"}
