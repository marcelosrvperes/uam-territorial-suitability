import os
from unittest.mock import patch

import geopandas as gpd
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

_EMPTY_OSM_RESULT = gpd.GeoDataFrame({"category": []}, geometry=[], crs="EPSG:4326")
_EMPTY_POINTS_RESULT = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")


@pytest.fixture(autouse=True)
def _no_live_osm_calls():
    """Every test in this module mocks all OSM fetches — Overpass is a live,
    rate-limited public service (see D37); automated tests must not depend
    on it being reachable."""
    with (
        patch(
            "uam_territorial_suitability.api.routes.fetch_land_use_features",
            return_value=_EMPTY_OSM_RESULT,
        ),
        patch(
            "uam_territorial_suitability.api.routes.fetch_transit_nodes",
            return_value=_EMPTY_POINTS_RESULT,
        ),
        patch(
            "uam_territorial_suitability.api.routes.fetch_major_roads",
            return_value=_EMPTY_POINTS_RESULT,
        ),
    ):
        yield


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("REH_CORRIDORS_PATH", raising=False)
    monkeypatch.delenv("DTM_PATH", raising=False)
    monkeypatch.delenv("DSM_PATH", raising=False)
    routes._cached_reh_corridors.cache_clear()


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
    # land_use and proximity are always attempted (live OSM, no config gate)
    # — mocked to empty results above, so they come back "computed".
    for criterion_id in ["obstacles", "heliport_retrofit", "topography"]:
        assert body["criteria"][criterion_id]["status"] == "not_implemented"
    assert body["criteria"]["land_use"]["status"] == "computed"
    assert body["criteria"]["proximity"]["status"] == "computed"
    assert "parcial" in body["note"].lower()
    assert body["aptitude"] is None


def test_aptitude_skips_topography_for_elevated_site(monkeypatch: pytest.MonkeyPatch) -> None:
    """D47: a rooftop/elevated site has no bare-earth DTM underneath it — the
    endpoint must not even attempt the DTM read, not just discard a garbage
    result."""
    monkeypatch.setenv("DTM_PATH", "dummy_not_read.tif")
    with patch("uam_territorial_suitability.api.routes.mean_slope_percent") as mocked:
        payload = {**VALID_PAYLOAD, "elevated_heliport": True}
        response = client.post("/api/aptitude", json=payload)
        mocked.assert_not_called()
    body = response.json()
    assert body["criteria"]["topography"]["status"] == "not_implemented"
    assert "elevat" in body["criteria"]["topography"]["detail"].lower()


def test_aptitude_proximity_computed_via_mocked_osm() -> None:
    response = client.post("/api/aptitude", json=VALID_PAYLOAD)
    body = response.json()
    assert body["criteria"]["proximity"]["status"] == "computed"
    assert body["criteria"]["proximity"]["value"] == 0.0  # nothing nearby -> worst case


def test_aptitude_land_use_computed_via_mocked_osm() -> None:
    response = client.post("/api/aptitude", json=VALID_PAYLOAD)
    body = response.json()
    assert body["criteria"]["land_use"]["status"] == "computed"
    assert body["criteria"]["land_use"]["value"] == 1.0  # no features -> best-case score


def test_aptitude_airspace_light_not_implemented_without_env_var() -> None:
    response = client.post("/api/aptitude", json=VALID_PAYLOAD)
    assert response.json()["criteria"]["airspace_light"]["status"] == "not_implemented"


@pytest.mark.skipif(
    not os.environ.get("UAM_TEST_REH_PATH"),
    reason="Set UAM_TEST_REH_PATH to a real REH shapefile to run this integration test",
)
def test_aptitude_airspace_light_computed_with_real_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REH_CORRIDORS_PATH", os.environ["UAM_TEST_REH_PATH"])
    routes._cached_reh_corridors.cache_clear()
    response = client.post("/api/aptitude", json=VALID_PAYLOAD)
    outcome = response.json()["criteria"]["airspace_light"]
    assert outcome["status"] == "computed"
    assert 0.0 <= outcome["value"] <= 1.0


def test_aptitude_heliport_retrofit_requires_geometry_and_obstacles() -> None:
    response = client.post("/api/aptitude", json=VALID_PAYLOAD)
    body = response.json()
    # obstacles is not_implemented (no DSM_PATH) -> heliport_retrofit can't be computed either.
    assert body["criteria"]["heliport_retrofit"]["status"] == "not_implemented"


def test_aptitude_land_use_reports_failure_on_network_error() -> None:
    import requests

    with patch(
        "uam_territorial_suitability.api.routes.fetch_land_use_features",
        side_effect=requests.HTTPError("504 Gateway Timeout"),
    ):
        response = client.post("/api/aptitude", json=VALID_PAYLOAD)
    assert response.json()["criteria"]["land_use"]["status"] == "failed"
