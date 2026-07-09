"""Loaders for the raw geospatial sources catalogued in the thesis methodology.

See 13-Camada2/03-dados/fontes_identificadas.md and dicionario_dados.md for the
full provenance of each source. This module only knows how to *read* a file
given its path — it does not know where any specific user's copy of the data
lives (no personal Drive paths hardcoded here, per D07: the tool must stay
usable by any municipality/user, not just this thesis's dataset).

Working CRS convention (dicionario_dados.md): everything is reprojected to
EPSG:31983 (SIRGAS 2000 / UTM 23S) on ingestion.
"""

from pathlib import Path

import geopandas as gpd

WORKING_CRS = "EPSG:31983"

# heliport.shp / airport.shp (ANAC/DECEA) are known to have Latin-1-encoded
# text fields (D18) — "São Paulo" reads as "S�o Paulo" under UTF-8.
_ANAC_DECEA_ENCODING = "latin1"


def load_heliports_airports(path: str | Path) -> gpd.GeoDataFrame:
    """Load the ANAC/DECEA heliport or airport shapefile.

    Expects the schema documented in dicionario_dados.md item 1 (ciad,
    localidade, nome, tipo, tipo_util, cidade, uf, airport_pk, geometry, ...).
    """
    gdf = gpd.read_file(path, encoding=_ANAC_DECEA_ENCODING)
    return gdf.to_crs(WORKING_CRS)


def load_reh_corridors(path: str | Path) -> gpd.GeoDataFrame:
    """Load the DECEA REH (Rotas Especiais de Helicóptero) corridor polygons.

    Expects the schema documented in dicionario_dados.md item 2 (tipo, nome,
    semi_largu, altmax, altmin, geometry as Polygon, ...). Same encoding
    caveat as the ANAC/DECEA data.
    """
    gdf = gpd.read_file(path, encoding=_ANAC_DECEA_ENCODING)
    return gdf.to_crs(WORKING_CRS)


def filter_to_bbox(gdf: gpd.GeoDataFrame, bbox: tuple[float, float, float, float]) -> gpd.GeoDataFrame:
    """Clip a GeoDataFrame (already in WORKING_CRS) to a bounding box in the same CRS.

    Used to restrict a nationwide dataset (e.g. all 4,383 ANAC aerodromes) to
    the pilot case region (RMSP) before running any criteria computation.
    """
    minx, miny, maxx, maxy = bbox
    return gdf.cx[minx:maxx, miny:maxy]
