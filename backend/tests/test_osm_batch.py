from unittest.mock import MagicMock, patch

import pytest
import requests

from uam_territorial_suitability.osm_batch import (
    fetch_land_use_features_bbox,
    fetch_major_roads_bbox,
    fetch_transit_nodes_bbox,
)

_FAKE_LAND_USE_RESPONSE = {
    "elements": [
        {"tags": {"amenity": "school"}, "lat": -23.561, "lon": -46.656},
        {"tags": {"amenity": "clinic"}, "lat": -23.5615, "lon": -46.6565},
        {"tags": {"amenity": "restaurant"}, "lat": -23.5612, "lon": -46.6562},  # unmapped, ignored
    ]
}
_FAKE_TRANSIT_RESPONSE = {
    "elements": [
        {"lat": -23.561, "lon": -46.656},
        {"lat": -23.562, "lon": -46.657},
    ]
}
_FAKE_ROADS_RESPONSE = {
    "elements": [
        {"center": {"lat": -23.561, "lon": -46.656}},
        {"center": {"lat": -23.562, "lon": -46.657}},
    ]
}


def _mock_response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def test_land_use_bbox_maps_tags_and_uses_bbox_query() -> None:
    mock_post = MagicMock(return_value=_mock_response(_FAKE_LAND_USE_RESPONSE))
    with patch("uam_territorial_suitability.osm_batch.requests.post", mock_post):
        features = fetch_land_use_features_bbox(south=-23.7, west=-46.8, north=-23.4, east=-46.4)

    assert len(features) == 2  # restaurant dropped
    assert set(features["category"]) == {"school", "medical_clinic"}
    query = mock_post.call_args.kwargs["data"]["data"]
    assert "-23.7,-46.8,-23.4,-46.4" in query
    assert "around" not in query  # bbox query, not per-point radius


def test_transit_bbox_returns_points() -> None:
    with patch(
        "uam_territorial_suitability.osm_batch.requests.post",
        return_value=_mock_response(_FAKE_TRANSIT_RESPONSE),
    ):
        nodes = fetch_transit_nodes_bbox(south=-23.7, west=-46.8, north=-23.4, east=-46.4)
    assert len(nodes) == 2
    assert nodes.crs.to_string() == "EPSG:4326"


def test_roads_bbox_uses_way_centers() -> None:
    with patch(
        "uam_territorial_suitability.osm_batch.requests.post",
        return_value=_mock_response(_FAKE_ROADS_RESPONSE),
    ):
        roads = fetch_major_roads_bbox(south=-23.7, west=-46.8, north=-23.4, east=-46.4)
    assert len(roads) == 2


def test_raises_on_http_error() -> None:
    response = MagicMock()
    response.status_code = 504
    response.raise_for_status.side_effect = requests.HTTPError("504 Gateway Timeout")
    with (
        patch("uam_territorial_suitability.osm_batch.requests.post", return_value=response),
        pytest.raises(requests.HTTPError),
    ):
        fetch_land_use_features_bbox(south=-23.7, west=-46.8, north=-23.4, east=-46.4)


def test_retries_on_429_then_succeeds() -> None:
    rate_limited = MagicMock(status_code=429)
    ok = _mock_response(_FAKE_TRANSIT_RESPONSE)
    ok.status_code = 200
    mock_post = MagicMock(side_effect=[rate_limited, ok])
    with (
        patch("uam_territorial_suitability.osm_batch.requests.post", mock_post),
        patch("uam_territorial_suitability.osm_batch.time.sleep"),
    ):
        nodes = fetch_transit_nodes_bbox(south=-23.7, west=-46.8, north=-23.4, east=-46.4)
    assert len(nodes) == 2
    assert mock_post.call_count == 2


def test_gives_up_after_max_retries_on_persistent_429() -> None:
    rate_limited = MagicMock(status_code=429)
    mock_post = MagicMock(return_value=rate_limited)
    with (
        patch("uam_territorial_suitability.osm_batch.requests.post", mock_post),
        patch("uam_territorial_suitability.osm_batch.time.sleep"),
        pytest.raises(requests.HTTPError),
    ):
        fetch_transit_nodes_bbox(south=-23.7, west=-46.8, north=-23.4, east=-46.4)
