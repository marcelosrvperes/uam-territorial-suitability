import geopandas as gpd
import pytest
from shapely.geometry import Point, Polygon

from uam_territorial_suitability.criteria_airspace import (
    airspace_light_score,
    distance_to_nearest_corridor,
)


@pytest.fixture
def one_corridor() -> gpd.GeoDataFrame:
    # A 100x100 m square corridor centered at the origin.
    square = Polygon([(-50, -50), (50, -50), (50, 50), (-50, 50)])
    return gpd.GeoDataFrame({"nome": ["corridor-1"]}, geometry=[square], crs="EPSG:31983")


def test_site_inside_corridor_has_zero_distance(one_corridor: gpd.GeoDataFrame) -> None:
    site = Point(0, 0)
    assert distance_to_nearest_corridor(site, one_corridor) == 0.0


def test_site_outside_corridor_has_positive_distance(one_corridor: gpd.GeoDataFrame) -> None:
    site = Point(150, 0)  # 100 m from the corridor edge at x=50
    assert distance_to_nearest_corridor(site, one_corridor) == pytest.approx(100.0)


def test_empty_corridors_gives_infinite_distance() -> None:
    empty = gpd.GeoDataFrame({"nome": []}, geometry=[], crs="EPSG:31983")
    assert distance_to_nearest_corridor(Point(0, 0), empty) == float("inf")


def test_score_is_one_inside_corridor(one_corridor: gpd.GeoDataFrame) -> None:
    assert airspace_light_score(Point(0, 0), one_corridor) == 1.0


def test_score_decays_linearly_with_distance(one_corridor: gpd.GeoDataFrame) -> None:
    # 1000 m from the edge, halfway to the 2000 m cutoff -> score ~0.5
    site = Point(1050, 0)
    assert airspace_light_score(site, one_corridor) == pytest.approx(0.5, abs=1e-6)


def test_score_is_zero_beyond_max_distance(one_corridor: gpd.GeoDataFrame) -> None:
    site = Point(5000, 0)
    assert airspace_light_score(site, one_corridor) == 0.0
