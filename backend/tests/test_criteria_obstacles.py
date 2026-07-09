import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from uam_territorial_suitability.criteria_obstacles import (
    find_ofv_violations,
    obstacles_score,
    ofv_allowed_height,
    ofv_scan_radius_m,
)

D = 16.0  # reference aircraft dimension, matches criterios_aptidao.md hypothesis
R_FATO = 2.83 / 2 * D  # 22.64 m
R_H2 = 5.0 / 2 * D  # 40.0 m


def test_allowed_height_at_center_is_h1() -> None:
    assert ofv_allowed_height(0.0, D) == pytest.approx(3.0)


def test_allowed_height_at_fato_edge_is_h1() -> None:
    assert ofv_allowed_height(R_FATO, D) == pytest.approx(3.0)


def test_allowed_height_at_h2_radius_is_h2() -> None:
    assert ofv_allowed_height(R_H2, D) == pytest.approx(30.5)


def test_allowed_height_beyond_h2_radius_caps_at_h2() -> None:
    assert ofv_allowed_height(R_H2 + 500, D) == pytest.approx(30.5)


def test_allowed_height_increases_monotonically_between_fato_and_h2() -> None:
    midpoint = (R_FATO + R_H2) / 2
    low = ofv_allowed_height(R_FATO + 1, D)
    mid = ofv_allowed_height(midpoint, D)
    high = ofv_allowed_height(R_H2 - 1, D)
    assert low < mid < high


def test_scan_radius_matches_r_h2() -> None:
    assert ofv_scan_radius_m(D) == pytest.approx(R_H2)


def _write_flat_dsm(path: str, elevation: float, size: int = 200, pixel_size: float = 2.0) -> None:
    data = np.full((size, size), elevation, dtype="float32")
    transform = from_origin(-size * pixel_size / 2, size * pixel_size / 2, pixel_size, pixel_size)
    with rasterio.open(
        path, "w", driver="GTiff", height=size, width=size, count=1, dtype="float32",
        crs="EPSG:31983", transform=transform, nodata=-9999.0,
    ) as dst:
        dst.write(data, 1)


def test_no_violations_on_flat_terrain_at_reference_elevation(tmp_path) -> None:
    path = str(tmp_path / "flat.tif")
    _write_flat_dsm(path, elevation=800.0)
    violations = find_ofv_violations(
        path, center_x=0, center_y=0, reference_elevation_m=800.0, aircraft_d_m=D
    )
    assert violations == []
    assert obstacles_score(violations) == 1.0


def test_violations_when_terrain_far_above_reference(tmp_path) -> None:
    path = str(tmp_path / "tower.tif")
    # Whole window is 50 m above reference — well above the h1=3m limit near
    # the center, so every pixel inside the scan radius violates.
    _write_flat_dsm(path, elevation=850.0)
    violations = find_ofv_violations(
        path, center_x=0, center_y=0, reference_elevation_m=800.0, aircraft_d_m=D
    )
    assert len(violations) > 0
    assert obstacles_score(violations) < 1.0


def test_obstacles_score_worse_with_larger_excess(tmp_path) -> None:
    low_path = str(tmp_path / "low.tif")
    high_path = str(tmp_path / "high.tif")
    _write_flat_dsm(low_path, elevation=805.0)  # 5 m above reference
    _write_flat_dsm(high_path, elevation=850.0)  # 50 m above reference
    low_violations = find_ofv_violations(low_path, 0, 0, 800.0, D)
    high_violations = find_ofv_violations(high_path, 0, 0, 800.0, D)
    assert obstacles_score(low_violations) > obstacles_score(high_violations)
