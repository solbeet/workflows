"""Tests de los endpoints del fixture."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_devuelve_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_sum_suma_los_parametros() -> None:
    response = client.get("/sum", params={"a": 2, "b": 3})
    assert response.status_code == 200
    assert response.json() == {"result": 5}


def test_sum_rechaza_no_enteros() -> None:
    response = client.get("/sum", params={"a": "x", "b": 3})
    assert response.status_code == 422
