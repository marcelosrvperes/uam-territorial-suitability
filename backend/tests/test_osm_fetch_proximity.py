from unittest.mock import MagicMock, patch

from uam_territorial_suitability.osm_fetch import fetch_major_roads, fetch_transit_nodes

_TRANSIT_RESPONSE = {
    "elements": [
        {"lat": -23.561, "lon": -46.656},
        {"lat": -23.562, "lon": -46.657},
    ]
}

_ROADS_RESPONSE = {
    "elements": [
        {"center": {"lat": -23.560, "lon": -46.655}},
        {"tags": {}},  # a way without "center" (e.g. query variant) — must be skipped, not crash
    ]
}


def _mock_response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def test_fetch_transit_nodes_returns_points() -> None:
    with patch(
        "uam_territorial_suitability.osm_fetch.requests.post",
        return_value=_mock_response(_TRANSIT_RESPONSE),
    ):
        result = fetch_transit_nodes(lat=-23.5613, lon=-46.6565, radius_m=500)
    assert len(result) == 2
    assert result.crs.to_string() == "EPSG:4326"


def test_fetch_major_roads_skips_elements_without_center() -> None:
    with patch(
        "uam_territorial_suitability.osm_fetch.requests.post",
        return_value=_mock_response(_ROADS_RESPONSE),
    ):
        result = fetch_major_roads(lat=-23.5613, lon=-46.6565, radius_m=500)
    assert len(result) == 1  # only the element with "center" survives
