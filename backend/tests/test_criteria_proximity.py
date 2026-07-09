import geopandas as gpd
import pytest
from shapely.geometry import Point

from uam_territorial_suitability.criteria_proximity import (
    AERONAUTICAL_FAVORABLE_DISTANCE_M,
    TRANSIT_FAVORABLE_DISTANCE_M,
    proximity_score,
)


def _points(*coords: tuple[float, float]) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(geometry=[Point(x, y) for x, y in coords], crs="EPSG:31983")


EMPTY = gpd.GeoDataFrame(geometry=[], crs="EPSG:31983")


def test_perfect_score_when_everything_at_site() -> None:
    site = Point(0, 0)
    result = proximity_score(site, _points((0, 0)), _points((0, 0)), _points((0, 0)))
    assert result.combined_score == pytest.approx(1.0)


def test_zero_score_when_nothing_nearby() -> None:
    site = Point(0, 0)
    result = proximity_score(site, EMPTY, EMPTY, EMPTY)
    assert result.combined_score == pytest.approx(0.0)


def test_transit_score_decays_to_half_at_midpoint() -> None:
    site = Point(0, 0)
    half_distance = TRANSIT_FAVORABLE_DISTANCE_M / 2
    result = proximity_score(site, _points((half_distance, 0)), EMPTY, EMPTY)
    assert result.transit_score == pytest.approx(0.5, abs=1e-6)


def test_aeronautical_score_uses_half_nm_threshold() -> None:
    site = Point(0, 0)
    just_inside = _points((AERONAUTICAL_FAVORABLE_DISTANCE_M - 1, 0))
    just_outside = _points((AERONAUTICAL_FAVORABLE_DISTANCE_M + 1, 0))
    inside_result = proximity_score(site, EMPTY, just_inside, EMPTY)
    outside_result = proximity_score(site, EMPTY, just_outside, EMPTY)
    assert inside_result.aeronautical_score > 0.0
    assert outside_result.aeronautical_score == 0.0


def test_combined_score_is_weighted_average_of_subscores() -> None:
    site = Point(0, 0)
    # Only transit present and at distance 0 -> transit_score=1, others=0.
    result = proximity_score(site, _points((0, 0)), EMPTY, EMPTY)
    assert result.combined_score == pytest.approx(0.45, abs=1e-6)
