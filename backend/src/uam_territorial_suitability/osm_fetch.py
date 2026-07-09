"""Fetch land-use features from OpenStreetMap via the Overpass API.

Kept separate from criteria_land_use.py's pure scoring logic (network I/O
vs. testable computation) and from data_sources.py (that module reads local
files; this one queries a live public API — no key/account required, per
D19). Consumed by any municipality's deployment, not tied to RMSP.
"""

import geopandas as gpd
import requests
from shapely.geometry import Point

from uam_territorial_suitability.criteria_land_use import OSM_TAG_TO_CATEGORY

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_REQUEST_TIMEOUT_S = 30
# Overpass rejects requests without an identifying User-Agent (406).
_HEADERS = {"User-Agent": "uam-territorial-suitability/0.1 (thesis research tool)"}

# OSM tag keys we query for, mapped through OSM_TAG_TO_CATEGORY's value
# vocabulary (amenity=hospital, amenity=school, ...).
_AMENITY_VALUES = list(OSM_TAG_TO_CATEGORY.keys())


def _build_query(lat: float, lon: float, radius_m: float) -> str:
    amenity_filter = "|".join(_AMENITY_VALUES)
    return f"""
    [out:json][timeout:{_REQUEST_TIMEOUT_S}];
    (
      node["amenity"~"^({amenity_filter})$"](around:{radius_m},{lat},{lon});
    );
    out center;
    """


def fetch_land_use_features(lat: float, lon: float, radius_m: float) -> gpd.GeoDataFrame:
    """Query Overpass for land-use features of interest around (lat, lon).

    Returns a GeoDataFrame in EPSG:4326 with a "category" column already
    mapped to `criteria_land_use.LAND_USE_COMPATIBILITY` vocabulary — ready
    to reproject and pass into `land_use_score`. Raises `requests.HTTPError`
    on network/API failure; callers should treat that as "criterion not
    computable right now", not as "no land use nearby".
    """
    query = _build_query(lat, lon, radius_m)
    response = requests.post(
        _OVERPASS_URL, data={"data": query}, headers=_HEADERS, timeout=_REQUEST_TIMEOUT_S
    )
    response.raise_for_status()
    elements = response.json().get("elements", [])

    categories = []
    geometries = []
    for element in elements:
        tag_value = element.get("tags", {}).get("amenity")
        category = OSM_TAG_TO_CATEGORY.get(tag_value)
        if category is None:
            continue
        categories.append(category)
        geometries.append(Point(element["lon"], element["lat"]))

    return gpd.GeoDataFrame({"category": categories}, geometry=geometries, crs="EPSG:4326")
