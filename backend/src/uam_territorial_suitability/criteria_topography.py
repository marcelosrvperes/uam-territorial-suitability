"""Criterion 7 — Topografia / declividade (exclusion filter, D27).

Source: ICAO Annex 14 Vol II — Heliports (used by analogy, no vertiport-
specific slope standard exists in FAA EB-105A / EASA PTS-VPT-DSN — see
criterios_aptidao.md criterion 7).

FATO mean slope must not exceed 3% in general, or 2% for an elevated
heliport (rooftop/structure). Local slope limits by helicopter performance
class (5%/7%) are not applied here — the tool only checks the more
conservative "mean slope" requirement, which is the binding constraint for a
compact vertiport FATO.

IMPORTANT — use a bare-earth DTM/MDT here, NOT the DSM/MDS used by
criteria_obstacles.py. Validated against the real Congonhas MDS (Gate G3):
feeding it a surface model instead of bare terrain produced a spurious 4.48%
"slope" at the ARP, an artifact of surface objects (pavement edges, nearby
structures) rather than actual ground grade. See criterios_aptidao.md
criterion 7 for the full note.
"""

import numpy as np
import rasterio
from rasterio.windows import from_bounds

MAX_MEAN_SLOPE_PERCENT_GROUND = 3.0
MAX_MEAN_SLOPE_PERCENT_ELEVATED = 2.0


def mean_slope_percent(dem_path: str, center_x: float, center_y: float, radius_m: float) -> float:
    """Mean slope (%) of a DEM/MDS window centered on (center_x, center_y).

    Coordinates must be in the same projected CRS as the raster (meters).
    Uses a simple finite-difference gradient (numpy.gradient) scaled by pixel
    size, which is adequate for a first-pass exclusion check — not a
    substitute for a proper as-built site survey.
    """
    with rasterio.open(dem_path) as src:
        window = from_bounds(
            center_x - radius_m,
            center_y - radius_m,
            center_x + radius_m,
            center_y + radius_m,
            transform=src.transform,
        )
        nodata = src.nodata
        fill_value = nodata if nodata is not None else np.nan
        data = src.read(1, window=window, boundless=True, fill_value=fill_value).astype("float64")
        pixel_size_x = abs(src.transform.a)
        pixel_size_y = abs(src.transform.e)

    if nodata is not None:
        data[data == nodata] = np.nan
    if data.size == 0 or np.all(np.isnan(data)):
        raise ValueError("DEM window has no valid data at the requested location")

    gy, gx = np.gradient(data, pixel_size_y, pixel_size_x)
    slope_fraction = np.sqrt(gx**2 + gy**2)
    return float(np.nanmean(slope_fraction)) * 100.0


def passes_topography(slope_percent: float, elevated: bool = False) -> bool:
    """Whether a site's mean slope satisfies the ICAO Annex 14 Vol II FATO limit."""
    limit = MAX_MEAN_SLOPE_PERCENT_ELEVATED if elevated else MAX_MEAN_SLOPE_PERCENT_GROUND
    return slope_percent <= limit
