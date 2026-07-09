"""Coarse-resolution topography screening — "triagem ampla" tier (D15).

Two-tier strategy (metodo_agregacao.md / criterios_aptidao.md, D15): a
coarse, RMSP-wide DEM for a first-pass screen of every candidate site, and
the high-resolution GeoSampa MDT (criteria_topography.mean_slope_percent)
only for sites within São Paulo municipality that pass the coarse screen.

Coarse DEM source: Open Topo Data (https://www.opentopodata.org/), a free
public API wrapping SRTM 30 m — no API key/account needed (D19), unlike
OpenTopography's API or a manual TopoData/INPE tile download. User
suggested TopoData/SRTM (2026-07-09) as the broad-coverage source; SRTM 30m
via this API was chosen over a manual TopoData tile download because it is
directly queryable per-point/per-batch, matching the same no-manual-step
principle already applied to REH/heliponto/OSM sources.
"""

import requests
from pydantic import BaseModel

_API_URL = "https://api.opentopodata.org/v1/srtm30m"
_REQUEST_TIMEOUT_S = 15
_HEADERS = {"User-Agent": "uam-territorial-suitability/0.1 (thesis research tool)"}

# Sampling baseline in degrees at RMSP's latitude (~23.5°S): 1 deg lat ~=
# 111.32 km; 1 deg lon ~= 111.32 km * cos(lat) ~= 102.1 km at this latitude.
#
# Deliberately NOT ~30 m (SRTM's native pixel size): a baseline that close to
# one pixel amplifies SRTM's per-pixel quantization/vertical noise (~1-2 m)
# into implausible slope readings — confirmed empirically (2026-07-09):
# Congonhas' runway, which should be near-flat, read as 17.7% slope at a 60 m
# baseline. A wider baseline trades local precision (this tier was never
# meant to resolve a single FATO's grade — that's the MDT tier's job) for a
# stable regional trend, which is what a "triagem ampla" screen needs.
_SAMPLING_BASELINE_M = 250.0
_LAT_OFFSET_DEG = _SAMPLING_BASELINE_M / 111_320
_LON_OFFSET_DEG = _SAMPLING_BASELINE_M / 102_100


class CoarseSlopeResult(BaseModel):
    center_elevation_m: float
    slope_percent: float


def _fetch_elevations(locations: list[tuple[float, float]]) -> list[float]:
    location_str = "|".join(f"{lat},{lon}" for lat, lon in locations)
    response = requests.get(
        _API_URL, params={"locations": location_str}, headers=_HEADERS, timeout=_REQUEST_TIMEOUT_S
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "OK":
        raise requests.HTTPError(f"Open Topo Data returned status={payload.get('status')}")
    return [r["elevation"] for r in payload["results"]]


def coarse_slope(lat: float, lon: float) -> CoarseSlopeResult:
    """Estimate local slope (%) from a 5-point cross sampled from SRTM 30m.

    A coarse, first-pass estimate only — resolution (~30 m) is too low to
    resolve a single FATO's local grade precisely. Intended to discard
    obviously unsuitable terrain (steep hillsides) before a site is
    considered for the high-resolution MDT check.
    """
    center = (lat, lon)
    north = (lat + _LAT_OFFSET_DEG, lon)
    south = (lat - _LAT_OFFSET_DEG, lon)
    east = (lat, lon + _LON_OFFSET_DEG)
    west = (lat, lon - _LON_OFFSET_DEG)

    elevations = _fetch_elevations([center, north, south, east, west])
    z_center, z_north, z_south, z_east, z_west = elevations

    full_baseline = 2 * _SAMPLING_BASELINE_M
    dz_dy = (z_north - z_south) / full_baseline
    dz_dx = (z_east - z_west) / full_baseline
    slope_fraction = (dz_dx**2 + dz_dy**2) ** 0.5

    return CoarseSlopeResult(center_elevation_m=z_center, slope_percent=slope_fraction * 100.0)
