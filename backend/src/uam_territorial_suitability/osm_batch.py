"""Batch OSM fetch for a whole bounding box, not one live call per site (D58).

osm_fetch.py's per-site `around:radius,lat,lon` queries work fine for a single
on-demand map click, but running them for 140+ sites in a loop hits Overpass's
rate limit (429, D37) — that's exactly the wall the AHP weight sensitivity
analysis (D57) hit for land_use/proximity. The fix isn't retrying harder, it's
querying differently: fetch every relevant feature in the target bounding box
ONCE, then score every site locally against that in-memory GeoDataFrame (pure
distance computation, already implemented in criteria_land_use.py and
criteria_proximity.py — those functions never assumed a pre-filtered radius).
"""

import time

import geopandas as gpd
import requests
from shapely.geometry import Point

from uam_territorial_suitability.criteria_land_use import OSM_TAG_TO_CATEGORY

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
# A whole-municipality query returns far more elements than a per-site
# `around` query — give Overpass more time before giving up.
_REQUEST_TIMEOUT_S = 180
_HEADERS = {"User-Agent": "uam-territorial-suitability/0.1 (thesis research tool)"}

_AMENITY_VALUES = list(OSM_TAG_TO_CATEGORY.keys())

# Even 3 large bbox queries in a row can trip Overpass's public-instance rate
# limit (429) — the batch approach cuts call *count* from 3*N to 3, but each
# call is heavier, and the limiter also weighs query cost/load. Retry with
# backoff rather than fail the whole batch over a transient 429 (D37 — known
# operational risk of the free public instance, not hidden).
_MAX_RETRIES = 4
_RETRY_BACKOFF_S = 20.0


def _run_query(query: str) -> list[dict]:
    last_error: requests.HTTPError | None = None
    for attempt in range(_MAX_RETRIES):
        response = requests.post(_OVERPASS_URL, data={"data": query}, headers=_HEADERS, timeout=_REQUEST_TIMEOUT_S)
        if response.status_code == 429:
            last_error = requests.HTTPError("429 Too Many Requests", response=response)
            time.sleep(_RETRY_BACKOFF_S * (attempt + 1))
            continue
        response.raise_for_status()
        return response.json().get("elements", [])
    raise last_error


def fetch_land_use_features_bbox(south: float, west: float, north: float, east: float) -> gpd.GeoDataFrame:
    """Every OSM amenity node of interest inside the bbox (WGS84 degrees)."""
    value_filter = "|".join(_AMENITY_VALUES)
    query = f"""
    [out:json][timeout:{_REQUEST_TIMEOUT_S}];
    (
      node["amenity"~"^({value_filter})$"]({south},{west},{north},{east});
    );
    out body;
    """
    elements = _run_query(query)
    categories, geometries = [], []
    for element in elements:
        tag_value = element.get("tags", {}).get("amenity")
        category = OSM_TAG_TO_CATEGORY.get(tag_value)
        if category is None:
            continue
        categories.append(category)
        geometries.append(Point(element["lon"], element["lat"]))
    return gpd.GeoDataFrame({"category": categories}, geometry=geometries, crs="EPSG:4326")


def fetch_transit_nodes_bbox(south: float, west: float, north: float, east: float) -> gpd.GeoDataFrame:
    """Every public-transport node inside the bbox (WGS84 degrees)."""
    query = f"""
    [out:json][timeout:{_REQUEST_TIMEOUT_S}];
    (
      node["public_transport"~"^(stop_position|station|platform)$"]({south},{west},{north},{east});
    );
    out body;
    """
    elements = _run_query(query)
    geometries = [Point(e["lon"], e["lat"]) for e in elements if "lon" in e and "lat" in e]
    return gpd.GeoDataFrame(geometry=geometries, crs="EPSG:4326")


def fetch_major_roads_bbox(south: float, west: float, north: float, east: float) -> gpd.GeoDataFrame:
    """Every major road way (centroid) inside the bbox (WGS84 degrees)."""
    value_filter = "|".join(["motorway", "trunk", "primary", "secondary"])
    query = f"""
    [out:json][timeout:{_REQUEST_TIMEOUT_S}];
    (
      way["highway"~"^({value_filter})$"]({south},{west},{north},{east});
    );
    out center;
    """
    elements = _run_query(query)
    geometries = [Point(e["center"]["lon"], e["center"]["lat"]) for e in elements if "center" in e]
    return gpd.GeoDataFrame(geometry=geometries, crs="EPSG:4326")
