import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from uam_territorial_suitability.criteria_topography import (
    mean_slope_percent,
    passes_topography,
)


def _write_ramp_dem(path: str, pixel_size: float, slope_fraction: float, size: int = 200) -> None:
    """Write a synthetic DEM that rises linearly in x at the given slope fraction."""
    x = np.arange(size) * pixel_size * slope_fraction
    data = np.tile(x, (size, 1)).astype("float32")
    transform = from_origin(0, size * pixel_size, pixel_size, pixel_size)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=size,
        width=size,
        count=1,
        dtype="float32",
        crs="EPSG:31983",
        transform=transform,
        nodata=-9999.0,
    ) as dst:
        dst.write(data, 1)


@pytest.fixture
def flat_dem(tmp_path) -> str:
    path = str(tmp_path / "flat.tif")
    _write_ramp_dem(path, pixel_size=1.0, slope_fraction=0.0)
    return path


@pytest.fixture
def one_percent_slope_dem(tmp_path) -> str:
    path = str(tmp_path / "ramp_1pct.tif")
    _write_ramp_dem(path, pixel_size=1.0, slope_fraction=0.01)
    return path


@pytest.fixture
def five_percent_slope_dem(tmp_path) -> str:
    path = str(tmp_path / "ramp_5pct.tif")
    _write_ramp_dem(path, pixel_size=1.0, slope_fraction=0.05)
    return path


def test_flat_dem_has_zero_slope(flat_dem: str) -> None:
    slope = mean_slope_percent(flat_dem, center_x=100, center_y=100, radius_m=20)
    assert slope == pytest.approx(0.0, abs=1e-6)


def test_one_percent_ramp_measures_close_to_one_percent(one_percent_slope_dem: str) -> None:
    slope = mean_slope_percent(one_percent_slope_dem, center_x=100, center_y=100, radius_m=20)
    assert slope == pytest.approx(1.0, abs=0.05)


def test_five_percent_ramp_measures_close_to_five_percent(five_percent_slope_dem: str) -> None:
    slope = mean_slope_percent(five_percent_slope_dem, center_x=100, center_y=100, radius_m=20)
    assert slope == pytest.approx(5.0, abs=0.1)


def test_passes_topography_ground_limit() -> None:
    assert passes_topography(2.9, elevated=False)
    assert not passes_topography(3.1, elevated=False)


def test_passes_topography_elevated_limit_is_stricter() -> None:
    assert passes_topography(1.9, elevated=True)
    assert not passes_topography(2.1, elevated=True)
    # Same slope, ground site still passes where elevated would not
    assert passes_topography(2.5, elevated=False)
    assert not passes_topography(2.5, elevated=True)
