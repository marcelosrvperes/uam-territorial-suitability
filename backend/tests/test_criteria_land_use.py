import geopandas as gpd
import pytest
from shapely.geometry import Point

from uam_territorial_suitability.criteria_land_use import (
    Compatibility,
    Zone,
    classify_zone,
    land_use_score,
)


def test_classify_zone_boundaries() -> None:
    assert classify_zone(0) == Zone.A
    assert classify_zone(60.96) == Zone.A  # exactly 200 ft
    assert classify_zone(61.0) == Zone.B
    assert classify_zone(216.408) == Zone.B  # exactly 710 ft
    assert classify_zone(216.5) == Zone.C
    assert classify_zone(304.80) == Zone.C  # exactly 1000 ft
    assert classify_zone(472.74) == Zone.BUFFER  # ~1551 ft
    assert classify_zone(1000.0) == Zone.OUTSIDE


def _feature(category: str, x: float, y: float) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame({"category": [category]}, geometry=[Point(x, y)], crs="EPSG:31983")


def test_no_features_gives_perfect_score() -> None:
    site = Point(0, 0)
    empty = gpd.GeoDataFrame({"category": []}, geometry=[], crs="EPSG:31983")
    score, finding = land_use_score(site, empty)
    assert score == 1.0
    assert finding is None


def test_hospital_in_zone_a_is_prohibited_and_heavily_penalized() -> None:
    site = Point(0, 0)
    features = _feature("hospital", 30, 0)  # 30 m -> Zone A
    score, finding = land_use_score(site, features)
    assert finding is not None
    assert finding.zone == Zone.A
    assert finding.compatibility == Compatibility.PROHIBITED
    # Zone A importance = 1.0, X value = 0.0 -> score = 1 - 1*(1-0) = 0.0
    assert score == pytest.approx(0.0)


def test_power_infrastructure_in_zone_b_is_permitted() -> None:
    site = Point(0, 0)
    features = _feature("power_infrastructure", 100, 0)  # Zone B
    score, finding = land_use_score(site, features)
    assert finding is not None
    assert finding.compatibility == Compatibility.PERMITTED
    assert score == pytest.approx(1.0)


def test_unknown_category_is_ignored() -> None:
    site = Point(0, 0)
    features = _feature("some_osm_tag_we_dont_map", 10, 0)
    score, finding = land_use_score(site, features)
    assert score == 1.0
    assert finding is None


def test_worst_finding_dominates_over_multiple_features() -> None:
    site = Point(0, 0)
    features = gpd.GeoDataFrame(
        {"category": ["power_infrastructure", "daycare"]},
        geometry=[Point(100, 0), Point(30, 0)],  # zone B permitted, zone A prohibited
        crs="EPSG:31983",
    )
    score, finding = land_use_score(site, features)
    assert finding is not None
    assert finding.category == "daycare"
    assert score == pytest.approx(0.0)


def test_feature_outside_buffer_zone_is_ignored() -> None:
    site = Point(0, 0)
    features = _feature("hospital", 1000, 0)  # well beyond the 472.74 m buffer
    score, finding = land_use_score(site, features)
    assert score == 1.0
    assert finding is None
