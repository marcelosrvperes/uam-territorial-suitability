"""Complete the AHP weight sensitivity dataset (D57) with land_use and
proximity, using the batch OSM fetch (D58) instead of one live call per site.

Fetches land-use amenities, transit nodes, and major roads ONCE for the
bounding box covering every site in the input JSON, then scores each site
locally against that pre-fetched data — 3 Overpass calls total, not 3*N.

Usage:
    .venv/Scripts/python.exe scripts/compute_batch_osm_criteria.py \
        --screening-json "path/to/screening_com_criterios_ponderados.json" \
        --heliport-shp "path/to/heliport.shp" \
        --airport-shp "path/to/airport.shp" \
        --out "path/to/screening_completo.json"
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from uam_territorial_suitability.criteria_land_use import ZONE_RADIUS_M, Zone, land_use_score
from uam_territorial_suitability.criteria_proximity import proximity_score
from uam_territorial_suitability.data_sources import load_heliports_airports
from uam_territorial_suitability.osm_batch import (
    fetch_land_use_features_bbox,
    fetch_major_roads_bbox,
    fetch_transit_nodes_bbox,
)

_MARGIN_M = ZONE_RADIUS_M[Zone.BUFFER]  # pad the bbox so edge sites aren't starved of context


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screening-json", required=True)
    parser.add_argument("--heliport-shp", required=True)
    parser.add_argument("--airport-shp", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    with open(args.screening_json, encoding="utf-8") as f:
        sites = json.load(f)

    xs = [s["x"] for s in sites]
    ys = [s["y"] for s in sites]
    bbox_31983 = gpd.GeoSeries(
        [Point(min(xs) - _MARGIN_M, min(ys) - _MARGIN_M), Point(max(xs) + _MARGIN_M, max(ys) + _MARGIN_M)],
        crs="EPSG:31983",
    ).to_crs("EPSG:4326")
    west, south = bbox_31983.iloc[0].x, bbox_31983.iloc[0].y
    east, north = bbox_31983.iloc[1].x, bbox_31983.iloc[1].y
    print(f"Bounding box (WGS84): south={south:.4f} west={west:.4f} north={north:.4f} east={east:.4f}")

    print("Fetching land-use amenities (1 call for the whole area)...")
    land_use = fetch_land_use_features_bbox(south, west, north, east).to_crs("EPSG:31983")
    print(f"  {len(land_use)} features")

    print("Fetching transit nodes (1 call)...")
    transit = fetch_transit_nodes_bbox(south, west, north, east).to_crs("EPSG:31983")
    print(f"  {len(transit)} features")

    print("Fetching major roads (1 call)...")
    roads = fetch_major_roads_bbox(south, west, north, east).to_crs("EPSG:31983")
    print(f"  {len(roads)} features")

    aeronautical = gpd.GeoDataFrame(
        pd.concat([
            load_heliports_airports(args.heliport_shp),
            load_heliports_airports(args.airport_shp),
        ], ignore_index=True),
        crs="EPSG:31983",
    )

    for site in sites:
        point = Point(site["x"], site["y"])
        lu_score, worst = land_use_score(point, land_use)
        site["land_use_score"] = lu_score
        site["land_use_worst_finding"] = worst.category if worst else None

        prox = proximity_score(point, transit, aeronautical, roads)
        site["proximity_score"] = prox.combined_score

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(sites, f, ensure_ascii=False, indent=2)

    print(f"\nScored {len(sites)} sites with land_use_score and proximity_score.")
    print(f"Saved: {args.out}")


if __name__ == "__main__":
    main()
