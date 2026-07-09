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


def test_noisy_flat_dem_is_not_inflated_by_pixel_noise(tmp_path) -> None:
    """Regression test for D46: real GeoSampa MDT cells carry +-0.1-0.15 m
    measurement noise (sparse ground points per 1 m cell) even where the true
    grade is flat/gentle. A per-pixel finite-difference gradient amplifies
    that noise into a spurious slope reading (observed: Congonhas' runway,
    truly ~2%, read as ~4.15% before this fix); a least-squares plane fit
    should average the noise out and recover the true near-zero grade.
    """
    size = 60
    rng = np.random.default_rng(46)
    base = np.zeros((size, size), dtype="float64")
    noisy = base + rng.uniform(-0.13, 0.13, size=(size, size))
    path = str(tmp_path / "noisy_flat.tif")
    transform = from_origin(0, size, 1.0, 1.0)
    with rasterio.open(
        path, "w", driver="GTiff", height=size, width=size, count=1,
        dtype="float64", crs="EPSG:31983", transform=transform, nodata=-9999.0,
    ) as dst:
        dst.write(noisy.astype("float32"), 1)

    slope = mean_slope_percent(path, center_x=30, center_y=30, radius_m=20)
    assert slope < 1.0  # true grade is 0%; old pixel-gradient code read ~10%+ here


def test_passes_topography_ground_limit() -> None:
    assert passes_topography(2.9, elevated=False)
    assert not passes_topography(3.1, elevated=False)


def test_passes_topography_elevated_limit_is_stricter() -> None:
    assert passes_topography(1.9, elevated=True)
    assert not passes_topography(2.1, elevated=True)
    # Same slope, ground site still passes where elevated would not
    assert passes_topography(2.5, elevated=False)
    assert not passes_topography(2.5, elevated=True)
