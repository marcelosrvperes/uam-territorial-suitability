import pytest
from fastapi.testclient import TestClient

from uam_territorial_suitability.api import routes
from uam_territorial_suitability.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("HELIPORT_PATH", raising=False)
    monkeypatch.delenv("AERODROME_PATH", raising=False)
    monkeypatch.delenv("DTM_PATH", raising=False)
    routes._cached_heliports_airports.cache_clear()


def test_site_type_without_any_config_returns_sem_registro() -> None:
    response = client.get("/api/site-type", params={"latitude": -23.5, "longitude": -46.6})
    assert response.status_code == 200
    body = response.json()
    assert body["site_type"] == "sem_registro"
    assert body["in_scope"] is True


def test_site_type_rejects_invalid_coordinates() -> None:
    response = client.get("/api/site-type", params={"latitude": 999.0, "longitude": -46.6})
    assert response.status_code == 422
