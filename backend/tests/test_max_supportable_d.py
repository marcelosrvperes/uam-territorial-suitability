import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from uam_territorial_suitability.criteria_obstacles import max_supportable_aircraft_d


def _write_dsm_with_tower(path: str, tower_height_above_ref: float, size: int = 400, pixel_size: float = 1.0) -> None:
    """Flat terrain at elevation 800, except a 4x4 m tower near one edge of
    the window (20 m from center) rising `tower_height_above_ref` above it."""
    data = np.full((size, size), 800.0, dtype="float32")
    center = size // 2
    tower_offset_px = int(20 / pixel_size)
    data[center - 2 : center + 2, center + tower_offset_px - 2 : center + tower_offset_px + 2] = (
        800.0 + tower_height_above_ref
    )
    transform = from_origin(-center * pixel_size, center * pixel_size, pixel_size, pixel_size)
    with rasterio.open(
        path, "w", driver="GTiff", height=size, width=size, count=1, dtype="float32",
        crs="EPSG:31983", transform=transform, nodata=-9999.0,
    ) as dst:
        dst.write(data, 1)


@pytest.fixture
def flat_dsm(tmp_path) -> str:
    path = str(tmp_path / "flat.tif")
    _write_dsm_with_tower(path, tower_height_above_ref=0.0)
    return path


@pytest.fixture
def dsm_with_tall_tower_20m_out(tmp_path) -> str:
    # 25 m tall tower, 20 m from center — well above the h1=3m limit that
    # applies within the r_fato radius for any D in the search range.
    path = str(tmp_path / "tower.tif")
    _write_dsm_with_tower(path, tower_height_above_ref=25.0)
    return path


def test_flat_terrain_supports_the_largest_searched_d(flat_dsm: str) -> None:
    result = max_supportable_aircraft_d(
        flat_dsm, center_x=0, center_y=0, reference_elevation_m=800.0,
        d_search_range_m=(1.0, 50.0),
    )
    assert result == 50.0


def test_nearby_tall_tower_caps_supportable_d(dsm_with_tall_tower_20m_out: str) -> None:
    result = max_supportable_aircraft_d(
        dsm_with_tall_tower_20m_out, center_x=0, center_y=0, reference_elevation_m=800.0,
        d_search_range_m=(1.0, 50.0),
    )
    # r_fato(D) = 1.415*D reaches 20 m at D ~= 14.13 m — beyond that D the
    # tower falls inside the r_fato radius, where the height limit is a
    # fixed 3 m, far below the 25 m tower. Below that D, the tower may still
    # sit in the h1->h2 funnel, capped by the interpolated allowed height.
    assert 0.0 < result < 20.0


def test_result_never_exceeds_search_range(flat_dsm: str) -> None:
    result = max_supportable_aircraft_d(
        flat_dsm, center_x=0, center_y=0, reference_elevation_m=800.0,
        d_search_range_m=(1.0, 30.0),
    )
    assert result <= 30.0
