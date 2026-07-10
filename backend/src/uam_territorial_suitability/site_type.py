"""Site-type detection for a candidate location (D52 typology).

Classifies a clicked point as one of the in-scope retrofit categories (an
existing heliponto — elevated or ground) or flags it as out of the Módulo 02
scope (aeródromo certificado, D52 — moved to a future module) or as having no
matching ANAC record at all (likely laje or a new proposal, not yet in the
database).

Motivation: without this, a user clicking the map gets no context at all
before triggering a full aptitude computation — every click looks the same
whether it lands on a real heliponto, a certified airport, or empty ground.
"""

from enum import Enum

import geopandas as gpd
import numpy as np
import rasterio
from pydantic import BaseModel
from rasterio.windows import from_bounds
from shapely.geometry import Point

# How close a click must land to an ANAC point to count as "this site" (D45:
# ANAC heliponto coordinates have real positional error, median ~1m but a
# long tail up to ~150m for some records — 50m is a compromise between
# missing real matches and false-matching a different nearby site).
_MATCH_TOLERANCE_M = 50.0

# Neighborhood used to estimate local ground level for the elevated/ground
# heuristic, and the low percentile used instead of a strict min (robust to
# single-pixel MDT noise, D43/D46).
_GROUND_SEARCH_RADIUS_M = 100.0
_GROUND_PERCENTILE = 5.0

# ARP vs. local ground difference above this is treated as "elevated" (D45
# showed genuine rooftop cases sit tens of meters above street level).
_ELEVATED_THRESHOLD_M = 5.0


class SiteType(str, Enum):
    HELIPONTO = "heliponto"
    AERODROMO = "aerodromo"  # fora de escopo do Módulo 02, D52
    SEM_REGISTRO = "sem_registro"  # sem registro ANAC — laje ou proposta nova


class SiteTypeResult(BaseModel):
    site_type: SiteType
    ciad: str | None = None
    nome: str | None = None
    elevacao_m: float | None = None
    elevated: bool | None = None  # None = not determined (no DTM configured, or no ground data nearby)
    in_scope: bool
    note: str


def _nearest_match(point: Point, gdf: gpd.GeoDataFrame) -> tuple[float, "gpd.GeoSeries | None"]:
    if gdf.empty:
        return float("inf"), None
    distances = gdf.geometry.distance(point)
    idx = distances.idxmin()
    return float(distances.loc[idx]), gdf.loc[idx]


def _local_ground_level(dtm_path: str, x: float, y: float, radius_m: float) -> float | None:
    with rasterio.open(dtm_path) as src:
        window = from_bounds(
            x - radius_m, y - radius_m, x + radius_m, y + radius_m, transform=src.transform,
        )
        nodata = src.nodata
        fill_value = nodata if nodata is not None else np.nan
        data = src.read(1, window=window, boundless=True, fill_value=fill_value).astype("float64")
    if nodata is not None:
        data[data == nodata] = np.nan
    if np.all(np.isnan(data)):
        return None
    return float(np.nanpercentile(data[~np.isnan(data)], _GROUND_PERCENTILE))


def detect_site_type(
    x: float,
    y: float,
    heliports: gpd.GeoDataFrame,
    aerodromes: gpd.GeoDataFrame,
    dtm_path: str | None,
) -> SiteTypeResult:
    """`x`/`y` must be in the same projected CRS as the input GeoDataFrames (meters)."""
    point = Point(x, y)

    ad_dist, ad_row = _nearest_match(point, aerodromes)
    if ad_dist <= _MATCH_TOLERANCE_M and ad_row is not None:
        return SiteTypeResult(
            site_type=SiteType.AERODROMO,
            ciad=ad_row.get("ciad"),
            nome=ad_row.get("nome"),
            elevacao_m=ad_row.get("elevacao"),
            in_scope=False,
            note="Aeródromo certificado — fora do escopo do Módulo 02 (D52). Ponto de partida do Módulo 03 (Zonas de Proteção).",
        )

    hp_dist, hp_row = _nearest_match(point, heliports)
    if hp_dist <= _MATCH_TOLERANCE_M and hp_row is not None:
        elevacao = hp_row.get("elevacao")
        elevated: bool | None = None
        if dtm_path is not None and elevacao is not None:
            ground = _local_ground_level(dtm_path, x, y, _GROUND_SEARCH_RADIUS_M)
            if ground is not None:
                elevated = (float(elevacao) - ground) > _ELEVATED_THRESHOLD_M
        note = "Heliponto existente"
        note += " (elevado)." if elevated is True else " (solo)." if elevated is False else " (elevado/solo não determinado — falta DTM ou dado de solo próximo)."
        return SiteTypeResult(
            site_type=SiteType.HELIPONTO,
            ciad=hp_row.get("ciad"),
            nome=hp_row.get("nome"),
            elevacao_m=elevacao,
            elevated=elevated,
            in_scope=True,
            note=note,
        )

    return SiteTypeResult(
        site_type=SiteType.SEM_REGISTRO,
        in_scope=True,
        note="Sem registro na base ANAC — pode ser laje (rodoviária/shopping/outro uso) ou proposta nova.",
    )
