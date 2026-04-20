from fastapi.testclient import TestClient

from backend import app


client = TestClient(app)


def test_health_endpoint_responds_ok():
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("status") == "ok"
    assert "mongodb" in payload
