"""Criterion 2 — Obstáculos físicos (weighted, D13/D26/D36).

Two normative paths depending on the candidate site (see
criterios_aptidao.md, criterion 2):
  1. Sites that are already a certified aerodrome (fixed runway) — use
     RBAC 154 / ICAO Annex 14 Vol I surfaces (see the absorbed "Artigo 01"
     pipeline, D13). Not implemented in this module.
  2. All other sites (heliport without a runway, free area) — use the
     vertiport-native Obstacle-Free Volume (OFV), EASA PTS-VPT-DSN Chapter D
     Subpart 2, "Reference Volume Type 1" (Table D-6/D-7, omnidirectional,
     aircraft-agnostic — no AFM data required). This module implements path 2.

Scope note (D36): only the near-site part of the OFV is implemented here —
the cylinder/funnel from ground level up to h2 = 30.5 m (100 ft), radius up
to 2.5*D. The EASA spec continues the obstacle-limitation cone from h2 up to
152 m (500 ft), extending roughly 1 km outward at a 12.5% gradient — that
outer extent is functionally an approach/departure corridor protection, not
a local site check, and is deliberately left to the future Módulo 05
(Corredores), consistent with the same reasoning as D11 for the REH
criterion. Read this module's radius as "how much clear space does this
specific candidate site need around itself", not "is the whole approach
corridor clear".
"""

import numpy as np
import rasterio
from pydantic import BaseModel
from rasterio.windows import from_bounds

# EASA PTS-VPT-DSN Table D-7 — Omnidirectional Reference Volume Type 1 (with SAs).
_H1_M = 3.0  # low hover height
_H2_M = 30.5  # high hover height
_FATO_OMNI_RADIUS_FACTOR = 2.83 / 2  # Ø FATO_omnidirectional = 2.83 D
_TO_OMNI_RADIUS_FACTOR = 5.0 / 2  # Ø TO_omnidirectional = 5 D


class ObstacleViolation(BaseModel):
    distance_m: float
    height_above_reference_m: float
    allowed_height_m: float
    excess_m: float


def ofv_allowed_height(distance_m: float, aircraft_d_m: float) -> float:
    """Max obstacle height (m above FATO reference elevation) at a given
    horizontal distance from the site center, per the near-site OFV (D36).

    Distances beyond the h2 radius are capped at h2 — this function does not
    model the extended approach/departure corridor (out of scope, see module
    docstring).
    """
    r_fato = _FATO_OMNI_RADIUS_FACTOR * aircraft_d_m
    r_h2 = _TO_OMNI_RADIUS_FACTOR * aircraft_d_m
    if distance_m <= r_fato:
        return _H1_M
    if distance_m >= r_h2:
        return _H2_M
    fraction = (distance_m - r_fato) / (r_h2 - r_fato)
    return _H1_M + fraction * (_H2_M - _H1_M)


def ofv_scan_radius_m(aircraft_d_m: float) -> float:
    """Radius (m) within which the near-site OFV applies — see D36."""
    return _TO_OMNI_RADIUS_FACTOR * aircraft_d_m


def find_ofv_violations(
    dsm_path: str,
    center_x: float,
    center_y: float,
    reference_elevation_m: float,
    aircraft_d_m: float,
) -> list[ObstacleViolation]:
    """Find MDS/DSM pixels that penetrate the near-site OFV around a candidate site.

    `center_x`/`center_y` must be in the same projected CRS as the raster
    (meters — see data_sources.WORKING_CRS). `reference_elevation_m` is the
    site's own ground elevation (FATO level), so heights are measured
    relative to the pad, not sea level. Uses the DSM/MDS (captures buildings/
    vegetation) deliberately — this is the obstacles criterion, unlike
    criteria_topography.py which needs bare-earth DTM/MDT.
    """
    radius = ofv_scan_radius_m(aircraft_d_m)
    with rasterio.open(dsm_path) as src:
        window = from_bounds(
            center_x - radius, center_y - radius, center_x + radius, center_y + radius,
            transform=src.transform,
        )
        nodata = src.nodata
        fill_value = nodata if nodata is not None else np.nan
        data = src.read(1, window=window, boundless=True, fill_value=fill_value).astype("float64")
        transform = src.window_transform(window)

    if nodata is not None:
        data[data == nodata] = np.nan

    rows, cols = np.indices(data.shape)
    xs, ys = rasterio.transform.xy(transform, rows.ravel(), cols.ravel())
    xs = np.asarray(xs).reshape(data.shape)
    ys = np.asarray(ys).reshape(data.shape)
    distances = np.sqrt((xs - center_x) ** 2 + (ys - center_y) ** 2)
    heights_above_reference = data - reference_elevation_m

    allowed_heights = np.vectorize(lambda d: ofv_allowed_height(d, aircraft_d_m))(distances)

    candidate_mask = (
        ~np.isnan(heights_above_reference)
        & (distances <= radius)
        & (heights_above_reference > allowed_heights)
    )

    violations = [
        ObstacleViolation(
            distance_m=float(distances[idx]),
            height_above_reference_m=float(heights_above_reference[idx]),
            allowed_height_m=float(allowed_heights[idx]),
            excess_m=float(heights_above_reference[idx] - allowed_heights[idx]),
        )
        for idx in zip(*np.nonzero(candidate_mask), strict=True)
    ]
    return violations


def obstacles_score(violations: list[ObstacleViolation]) -> float:
    """Normalized [0, 1] score — 1.0 means no OFV violations found."""
    if not violations:
        return 1.0
    worst_excess = max(v.excess_m for v in violations)
    # Fully penalize once the worst violation exceeds 10 m above the allowed
    # envelope — a placeholder normalization pending literature grounding
    # (same status as the other continuous-criterion normalizations, see
    # metodo_agregacao.md pendency list).
    return max(0.0, 1.0 - worst_excess / 10.0)
