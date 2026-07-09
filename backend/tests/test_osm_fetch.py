from unittest.mock import MagicMock, patch

import pytest
import requests

from uam_territorial_suitability.osm_fetch import fetch_land_use_features

_FAKE_OVERPASS_RESPONSE = {
    "elements": [
        {"tags": {"amenity": "school"}, "lat": -23.561, "lon": -46.656},
        {"tags": {"amenity": "school"}, "lat": -23.562, "lon": -46.657},
        {"tags": {"amenity": "clinic"}, "lat": -23.5615, "lon": -46.6565},
        {"tags": {"amenity": "restaurant"}, "lat": -23.5612, "lon": -46.6562},  # unmapped, ignored
    ]
}


def _mock_response() -> MagicMock:
    response = MagicMock()
    response.json.return_value = _FAKE_OVERPASS_RESPONSE
    response.raise_for_status.return_value = None
    return response


def test_fetch_maps_osm_tags_to_categories() -> None:
    with patch("uam_territorial_suitability.osm_fetch.requests.post", return_value=_mock_response()):
        features = fetch_land_use_features(lat=-23.5613, lon=-46.6565, radius_m=500)

    assert len(features) == 3  # the "restaurant" element is dropped (unmapped)
    assert set(features["category"]) == {"school", "medical_clinic"}
    assert features.crs.to_string() == "EPSG:4326"


def test_fetch_sends_user_agent_header() -> None:
    mock_post = MagicMock(return_value=_mock_response())
    with patch("uam_territorial_suitability.osm_fetch.requests.post", mock_post):
        fetch_land_use_features(lat=0, lon=0, radius_m=100)

    _, kwargs = mock_post.call_args
    assert "User-Agent" in kwargs["headers"]


def test_fetch_raises_on_http_error() -> None:
    response = MagicMock()
    response.raise_for_status.side_effect = requests.HTTPError("504 Gateway Timeout")
    with (
        patch("uam_territorial_suitability.osm_fetch.requests.post", return_value=response),
        pytest.raises(requests.HTTPError),
    ):
        fetch_land_use_features(lat=0, lon=0, radius_m=100)
