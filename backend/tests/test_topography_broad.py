from unittest.mock import MagicMock, patch

import pytest
import requests

from uam_territorial_suitability.topography_broad import coarse_slope


def _mock_response(elevations: list[float]) -> MagicMock:
    response = MagicMock()
    response.json.return_value = {
        "status": "OK",
        "results": [{"elevation": e} for e in elevations],
    }
    response.raise_for_status.return_value = None
    return response


def test_flat_terrain_gives_zero_slope() -> None:
    # center, north, south, east, west — all the same elevation
    with patch(
        "uam_territorial_suitability.topography_broad.requests.get",
        return_value=_mock_response([800.0, 800.0, 800.0, 800.0, 800.0]),
    ):
        result = coarse_slope(-23.5, -46.6)
    assert result.center_elevation_m == 800.0
    assert result.slope_percent == pytest.approx(0.0, abs=1e-6)


def test_uniform_north_south_gradient() -> None:
    # north 6m higher, south 6m lower than center; baseline = 2*250m = 500m
    # -> dz/dy = 12/500 = 0.024 -> 2.4%
    with patch(
        "uam_territorial_suitability.topography_broad.requests.get",
        return_value=_mock_response([800.0, 806.0, 794.0, 800.0, 800.0]),
    ):
        result = coarse_slope(-23.5, -46.6)
    assert result.slope_percent == pytest.approx(2.4, abs=1e-6)


def test_raises_on_non_ok_status() -> None:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"status": "INVALID_REQUEST"}
    with (
        patch("uam_territorial_suitability.topography_broad.requests.get", return_value=response),
        pytest.raises(requests.HTTPError),
    ):
        coarse_slope(-23.5, -46.6)
