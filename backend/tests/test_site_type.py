import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import Point

from uam_territorial_suitability.site_type import SiteType, detect_site_type

_EMPTY = gpd.GeoDataFrame({"ciad": [], "nome": [], "elevacao": []}, geometry=[], crs="EPSG:31983")


def _gdf(ciad: str, nome: str, elevacao: float, x: float, y: float) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"ciad": [ciad], "nome": [nome], "elevacao": [elevacao]},
        geometry=[Point(x, y)],
        crs="EPSG:31983",
    )


def _flat_dtm(path: str, ground_elevation: float, size: int = 200) -> None:
    data = np.full((size, size), ground_elevation, dtype="float32")
    transform = from_origin(0, size, 1.0, 1.0)
    with rasterio.open(
        path, "w", driver="GTiff", height=size, width=size, count=1,
        dtype="float32", crs="EPSG:31983", transform=transform, nodata=-9999.0,
    ) as dst:
        dst.write(data, 1)


def test_matches_aerodrome_within_tolerance() -> None:
    aerodromes = _gdf("SP0001", "Congonhas", 802.91, 100.0, 100.0)
    result = detect_site_type(105.0, 100.0, _EMPTY, aerodromes, dtm_path=None)
    assert result.site_type == SiteType.AERODROMO
    assert result.in_scope is False
    assert result.ciad == "SP0001"


def test_ignores_aerodrome_far_away() -> None:
    aerodromes = _gdf("SP0001", "Congonhas", 802.91, 100.0, 100.0)
    result = detect_site_type(5000.0, 5000.0, _EMPTY, aerodromes, dtm_path=None)
    assert result.site_type == SiteType.SEM_REGISTRO


def test_matches_heliport_and_flags_elevated(tmp_path) -> None:
    heliports = _gdf("SP0404", "Palacio dos Bandeirantes", 792.0, 100.0, 100.0)
    dtm_path = str(tmp_path / "dtm.tif")
    _flat_dtm(dtm_path, ground_elevation=770.0)  # 22m below ARP -> elevated
    result = detect_site_type(105.0, 100.0, heliports, _EMPTY, dtm_path=dtm_path)
    assert result.site_type == SiteType.HELIPONTO
    assert result.elevated is True
    assert result.in_scope is True


def test_matches_heliport_and_flags_ground_level(tmp_path) -> None:
    heliports = _gdf("SP0001", "Heliponto solo", 700.0, 100.0, 100.0)
    dtm_path = str(tmp_path / "dtm.tif")
    _flat_dtm(dtm_path, ground_elevation=699.0)  # only 1m below ARP -> ground
    result = detect_site_type(105.0, 100.0, heliports, _EMPTY, dtm_path=dtm_path)
    assert result.site_type == SiteType.HELIPONTO
    assert result.elevated is False


def test_matches_heliport_without_dtm_leaves_elevated_undetermined() -> None:
    heliports = _gdf("SP0404", "Palacio dos Bandeirantes", 792.0, 100.0, 100.0)
    result = detect_site_type(105.0, 100.0, heliports, _EMPTY, dtm_path=None)
    assert result.site_type == SiteType.HELIPONTO
    assert result.elevated is None


def test_no_match_returns_sem_registro() -> None:
    result = detect_site_type(0.0, 0.0, _EMPTY, _EMPTY, dtm_path=None)
    assert result.site_type == SiteType.SEM_REGISTRO
    assert result.in_scope is True


def test_aerodrome_match_takes_priority_over_heliport() -> None:
    """If a point somehow matches both within tolerance, an aeródromo match
    should win — treating it as OFV-scoreable would use the wrong norm (D52)."""
    aerodromes = _gdf("SP0001", "Congonhas", 802.91, 100.0, 100.0)
    heliports = _gdf("SP9999", "Heliponto proximo", 800.0, 110.0, 100.0)
    result = detect_site_type(105.0, 100.0, heliports, aerodromes, dtm_path=None)
    assert result.site_type == SiteType.AERODROMO
