import os

import pytest
from fastapi.testclient import TestClient

from uam_territorial_suitability.api import routes
from uam_territorial_suitability.main import app

client = TestClient(app)

VALID_PAYLOAD = {
    "latitude": -23.5,
    "longitude": -46.6,
    "available_diameter_m": 40.0,
    "aircraft_d_m": 16.0,
    "geometry_standard": "easa",
}


def test_aptitude_computes_geometry() -> None:
    response = client.post("/api/aptitude", json=VALID_PAYLOAD)
    assert response.status_code == 200
    body = response.json()
    assert body["criteria"]["geometry"]["status"] == "computed"
    assert body["criteria"]["geometry"]["value"] is True  # 40 m >= 32 m EASA safety area


def test_aptitude_geometry_fails_for_small_site() -> None:
    payload = {**VALID_PAYLOAD, "available_diameter_m": 10.0}
    response = client.post("/api/aptitude", json=payload)
    assert response.json()["criteria"]["geometry"]["value"] is False


def test_aptitude_rejects_invalid_diameter() -> None:
    payload = {**VALID_PAYLOAD, "available_diameter_m": -5.0}
    response = client.post("/api/aptitude", json=payload)
    assert response.status_code == 422


def test_aptitude_marks_unimplemented_criteria() -> None:
    response = client.post("/api/aptitude", json=VALID_PAYLOAD)
    body = response.json()
    for criterion_id in ["obstacles", "heliport_retrofit", "land_use", "proximity", "topography"]:
        assert body["criteria"][criterion_id]["status"] == "not_implemented"
    assert "parcial" in body["note"].lower()


def test_aptitude_airspace_light_not_implemented_without_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(routes._REH_CORRIDORS_PATH_ENV, raising=False)
    response = client.post("/api/aptitude", json=VALID_PAYLOAD)
    assert response.json()["criteria"]["airspace_light"]["status"] == "not_implemented"


@pytest.mark.skipif(
    not os.environ.get("UAM_TEST_REH_PATH"),
    reason="Set UAM_TEST_REH_PATH to a real REH shapefile to run this integration test",
)
def test_aptitude_airspace_light_computed_with_real_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(routes._REH_CORRIDORS_PATH_ENV, os.environ["UAM_TEST_REH_PATH"])
    routes._cached_reh_corridors.cache_clear()
    response = client.post("/api/aptitude", json=VALID_PAYLOAD)
    outcome = response.json()["criteria"]["airspace_light"]
    assert outcome["status"] == "computed"
    assert 0.0 <= outcome["value"] <= 1.0
