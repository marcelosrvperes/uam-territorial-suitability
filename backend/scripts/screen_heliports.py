"""Batch-screen every ANAC heliponto within a DSM's coverage for retrofit capacity (D40/D45).

For each heliponto, computes:
  - max_supportable_aircraft_d: largest reference aircraft diameter D the site
    can support without an OFV violation (D40, criteria_obstacles.py).
  - reliable: whether the ANAC-reported elevation (ARP) agrees with the DSM
    value at the site's exact coordinate within 5m (D45) — a large mismatch
    means the ANAC point is likely off the true rooftop, and the max_D result
    for that site should not be trusted at face value.

This is the reproducible version of the ad-hoc analysis behind D40/D45 —
kept in the repo (not a throwaway script) so the screening can be re-run
whenever the underlying data changes, consistent with IEEE Access's emphasis
on reproducible systems (D50).

Usage:
    .venv/Scripts/python.exe scripts/screen_heliports.py \
        --heliport-shp "path/to/heliport.shp" \
        --dsm "path/to/mds.tif" \
        --out "path/to/screening_results.json"
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from uam_territorial_suitability.criteria_obstacles import max_supportable_aircraft_d
from uam_territorial_suitability.data_sources import load_heliports_airports

_RELIABILITY_THRESHOLD_M = 5.0  # D45


def screen(heliport_shp: str, dsm_path: str) -> list[dict]:
    heliports = load_heliports_airports(heliport_shp)

    results: list[dict] = []
    with rasterio.open(dsm_path) as src:
        transform, raster_bounds = src.transform, src.bounds
        for _, row in heliports.iterrows():
            x, y = row.geometry.x, row.geometry.y
            if not (raster_bounds.left <= x <= raster_bounds.right and raster_bounds.bottom <= y <= raster_bounds.top):
                continue  # outside this DSM's coverage — not screenable

            elevacao = row.get("elevacao")
            if elevacao is None:
                continue

            r0, c0 = rasterio.transform.rowcol(transform, x, y)
            try:
                pixel = src.read(1, window=rasterio.windows.Window(c0, r0, 1, 1))[0, 0]
            except Exception:
                continue
            if np.isnan(pixel):
                continue

            reliable = abs(float(pixel) - float(elevacao)) <= _RELIABILITY_THRESHOLD_M
            max_d = max_supportable_aircraft_d(dsm_path, x, y, float(elevacao))

            results.append({
                "ciad": row.get("ciad"),
                "nome": row.get("nome"),
                "x": x,  # EPSG:31983 (WORKING_CRS, data_sources.py)
                "y": y,
                "elevacao_m": float(elevacao),
                "max_d_m": max_d,
                "reliable": reliable,
            })
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--heliport-shp", required=True)
    parser.add_argument("--dsm", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    results = screen(args.heliport_shp, args.dsm)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    n_reliable = sum(1 for r in results if r["reliable"])
    print(f"Screened {len(results)} heliports within DSM coverage ({n_reliable} reliable, D45).")
    print(f"Saved: {args.out}")


if __name__ == "__main__":
    main()
