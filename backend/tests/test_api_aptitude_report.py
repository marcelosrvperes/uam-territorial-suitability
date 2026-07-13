from unittest.mock import patch

import geopandas as gpd
import pytest
from fastapi.testclient import TestClient

from uam_territorial_suitability.api import routes
from uam_territorial_suitability.main import app

client = TestClient(app)

VALID_QUERY = {
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
    monkeypatch.delenv("HELIPORT_PATH", raising=False)
    monkeypatch.delenv("AERODROME_PATH", raising=False)
    routes._cached_reh_corridors.cache_clear()


def test_report_returns_html() -> None:
    response = client.get("/api/aptitude/report", params=VALID_QUERY)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


def test_report_contains_coordinates_and_criteria() -> None:
    response = client.get("/api/aptitude/report", params=VALID_QUERY)
    body = response.text
    assert "-23.500000" in body
    assert "-46.600000" in body
    assert "Geometria e dimens" in body  # "Geometria e dimensões mínimas" (accent-safe substring)
    assert "Obst" in body  # "Obstáculos físicos"


def test_report_shows_partial_result_note_when_incomplete() -> None:
    response = client.get("/api/aptitude/report", params=VALID_QUERY)
    body = response.text
    assert "Resultado parcial" in body


def test_report_rejects_invalid_diameter() -> None:
    payload = {**VALID_QUERY, "available_diameter_m": -5.0}
    response = client.get("/api/aptitude/report", params=payload)
    assert response.status_code == 422


def test_report_shows_no_anac_registration_when_no_site_type_sources_configured() -> None:
    response = client.get("/api/aptitude/report", params=VALID_QUERY)
    assert "Tipo de s" not in response.text  # site type block omitted, no HELIPORT_PATH/AERODROME_PATH
