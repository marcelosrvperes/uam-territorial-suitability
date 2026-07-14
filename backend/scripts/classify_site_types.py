"""Augment the heliport screening JSON with the elevated/ground classification
(D55's heuristic, site_type.py) for each screened site.

Motivation: the screening JSON (screen_heliports.py) already has real
retrofit-capacity results (max_d_m, reliable) per site, but no site-type
label — so the article's screening figure cannot currently show whether
retrofit capacity differs between elevated (rooftop) and ground heliports.
This script reuses the exact same ground-level heuristic already implemented
and tested for the interactive map's site-type detection (site_type.py,
_local_ground_level/_ELEVATED_THRESHOLD_M/_GROUND_SEARCH_RADIUS_M/
_GROUND_PERCENTILE) rather than re-deriving a second copy of the same logic,
so the two can never silently drift apart.

Usage:
    .venv/Scripts/python.exe scripts/classify_site_types.py \
        --screening-json "path/to/screening_151_helipontos.json" \
        --dtm "path/to/mdt_SP_completo.tif" \
        --out "path/to/screening_com_tipo_sitio.json"
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from uam_territorial_suitability.site_type import (
    _ELEVATED_THRESHOLD_M,
    _GROUND_PERCENTILE,
    _GROUND_SEARCH_RADIUS_M,
    _local_ground_level,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screening-json", required=True)
    parser.add_argument("--dtm", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    with open(args.screening_json, encoding="utf-8") as f:
        sites = json.load(f)

    n_elevated = n_ground = n_undetermined = 0
    for site in sites:
        ground = _local_ground_level(args.dtm, site["x"], site["y"], _GROUND_SEARCH_RADIUS_M)
        if ground is None:
            site["elevated"] = None
            site["local_ground_m"] = None
            n_undetermined += 1
            continue
        elevated = (site["elevacao_m"] - ground) > _ELEVATED_THRESHOLD_M
        site["elevated"] = elevated
        site["local_ground_m"] = ground
        if elevated:
            n_elevated += 1
        else:
            n_ground += 1

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(sites, f, ensure_ascii=False, indent=2)

    print(
        f"Classified {len(sites)} sites: {n_elevated} elevated, {n_ground} ground, "
        f"{n_undetermined} undetermined (no valid DTM coverage within "
        f"{_GROUND_SEARCH_RADIUS_M:.0f}m, threshold={_ELEVATED_THRESHOLD_M:.0f}m, "
        f"ground-level percentile={_GROUND_PERCENTILE:.0f})."
    )
    print(f"Saved: {args.out}")


if __name__ == "__main__":
    main()
