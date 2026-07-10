"""Augment the heliport screening JSON with the two weighted criteria that can
be computed at scale without a live API (D57 — AHP weight sensitivity analysis).

obstacles and airspace_light are both local computations (DSM raster, REH
shapefile) — no rate limit. land_use and proximity need live OSM Overpass
calls per site (D19/D37); running those for 140+ sites needs a batch-fetch
architecture (fetch once for the whole area, compute distances locally) that
hasn't been built yet — see the note this script prints. Until then, any
sensitivity analysis built on this data covers 2 of the 4 weighted criteria,
not all 4 — that limitation must be stated explicitly wherever this is used.

Usage:
    .venv/Scripts/python.exe scripts/compute_weighted_criteria.py \
        --screening-json "path/to/screening_151_helipontos.json" \
        --dsm "path/to/mds.tif" \
        --reh-shp "path/to/CV_REH_XP_SAO_PAULO.shp" \
        --aircraft-d 16.0 \
        --out "path/to/screening_with_weighted_criteria.json"
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from shapely.geometry import Point

from uam_territorial_suitability.criteria_airspace import airspace_light_score
from uam_territorial_suitability.criteria_obstacles import find_ofv_violations, obstacles_score
from uam_territorial_suitability.data_sources import load_reh_corridors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screening-json", required=True)
    parser.add_argument("--dsm", required=True)
    parser.add_argument("--reh-shp", required=True)
    parser.add_argument("--aircraft-d", type=float, default=16.0)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    with open(args.screening_json, encoding="utf-8") as f:
        sites = json.load(f)

    reh = load_reh_corridors(args.reh_shp)

    for site in sites:
        violations = find_ofv_violations(
            args.dsm, center_x=site["x"], center_y=site["y"],
            reference_elevation_m=site["elevacao_m"], aircraft_d_m=args.aircraft_d,
        )
        site["obstacles_score"] = obstacles_score(violations)
        site["airspace_light_score"] = airspace_light_score(Point(site["x"], site["y"]), reh)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(sites, f, ensure_ascii=False, indent=2)

    print(f"Augmented {len(sites)} sites with obstacles_score (D={args.aircraft_d}m) and airspace_light_score.")
    print("NOTE: land_use and proximity scores are NOT included — need OSM batch-fetch (not built yet).")
    print(f"Saved: {args.out}")


if __name__ == "__main__":
    main()
