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

IMPORTANT — do not call this against a DTM for an elevated/rooftop site
(D47): there is no bare earth under a rooftop pad to sample. Validated
against real rooftop heliport data: the DTM window is mostly NoData there,
and what little valid terrain leaks in is street level tens of meters below
the pad, producing physically nonsensical slope readings. The caller
(api/routes.py) skips this function entirely when `elevated_heliport=True`.
"""

import numpy as np
import rasterio
from rasterio.windows import from_bounds

MAX_MEAN_SLOPE_PERCENT_GROUND = 3.0
MAX_MEAN_SLOPE_PERCENT_ELEVATED = 2.0


def mean_slope_percent(dem_path: str, center_x: float, center_y: float, radius_m: float) -> float:
    """Mean slope (%) of a DEM/MDT window centered on (center_x, center_y).

    Coordinates must be in the same projected CRS as the raster (meters).
    Fits a first-order plane (z = a + b*x + c*y) to the window by least
    squares and reports the plane's own gradient magnitude sqrt(b^2 + c^2).

    A plane fit, not a per-pixel finite-difference gradient (D46): validated
    against the real GeoSampa MDT (1 m/cell, min-Z-per-cell from sparse
    ground-classified LiDAR points — see D43), the raw grid has genuine
    pixel-to-pixel measurement noise of +-0.1-0.15 m even where the true
    underlying grade is smooth (e.g. Congonhas' runway, +-0.3 m over 16 m).
    numpy.gradient differentiates that noise directly, inflating a true ~2%
    grade to a spurious ~4% reading — the same class of quantization-noise
    bug already fixed for the coarse SRTM screening (D44), now at 1 m scale.
    A least-squares plane, unlike per-pixel differencing, averages the noise
    out across every point in the window instead of amplifying it.
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
        transform = src.window_transform(window)

    if nodata is not None:
        data[data == nodata] = np.nan
    if data.size == 0 or np.all(np.isnan(data)):
        raise ValueError("DEM window has no valid data at the requested location")

    rows, cols = np.indices(data.shape)
    xs, ys = rasterio.transform.xy(transform, rows.ravel(), cols.ravel())
    xs = np.asarray(xs)
    ys = np.asarray(ys)
    zs = data.ravel()
    valid = ~np.isnan(zs)
    xs, ys, zs = xs[valid], ys[valid], zs[valid]

    design = np.column_stack([np.ones_like(xs), xs, ys])
    _, slope_x, slope_y = np.linalg.lstsq(design, zs, rcond=None)[0]
    slope_fraction = float(np.hypot(slope_x, slope_y))
    return slope_fraction * 100.0


def passes_topography(slope_percent: float, elevated: bool = False) -> bool:
    """Whether a site's mean slope satisfies the ICAO Annex 14 Vol II FATO limit."""
    limit = MAX_MEAN_SLOPE_PERCENT_ELEVATED if elevated else MAX_MEAN_SLOPE_PERCENT_GROUND
    return slope_percent <= limit
