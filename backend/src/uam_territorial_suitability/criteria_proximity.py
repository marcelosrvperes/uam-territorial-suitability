"""Criterion 5 — Proximidade a infraestrutura (weighted, D28).

Sources: Wei et al. (2023, Mineta Transportation Institute) and Ison/WSDOT —
see criterios_aptidao.md criterion 5. Unlike criterion 4 (land use), this
criterion rewards *closeness*: proximity to transit and to existing
aeronautical infrastructure is favorable (accessibility, reuse), not a
conflict to avoid.

Explicit simplification (documented, not silently omitted): "10-min drive to
a major employer" from Wei et al. is not implemented — it requires road-
network routing, not just straight-line distance, which this module does not
attempt. Only transit-node, aeronautical-infrastructure and major-road
proximity are modeled.
"""

import geopandas as gpd
from pydantic import BaseModel
from shapely.geometry.base import BaseGeometry

# Favorable distance thresholds (beyond which the sub-score is 0), converted
# from Wei et al. (2023) and Ison/WSDOT — see criterios_aptidao.md.
TRANSIT_FAVORABLE_DISTANCE_M = 0.25 * 1609.34  # 402.3 m (quarter-mile walk)
AERONAUTICAL_FAVORABLE_DISTANCE_M = 0.5 * 1852.0  # 926.0 m (half nautical mile)
# Road proximity is explicitly "low priority" in Wei et al. — a looser,
# provisional threshold pending better literature grounding (same status as
# other normalization placeholders, see metodo_agregacao.md).
ROAD_FAVORABLE_DISTANCE_M = 300.0

# Sub-weights within this criterion (not the top-level AHP weights) —
# provisional, favors the two factors with concrete literature-backed
# distances over the looser road proximity.
_SUB_WEIGHTS = {"transit": 0.45, "aeronautical": 0.45, "road": 0.10}


class ProximityBreakdown(BaseModel):
    transit_score: float
    aeronautical_score: float
    road_score: float
    combined_score: float


def _linear_decay_score(distance_m: float, favorable_distance_m: float) -> float:
    if distance_m <= 0:
        return 1.0
    if distance_m >= favorable_distance_m:
        return 0.0
    return 1.0 - distance_m / favorable_distance_m


def _nearest_distance(site: BaseGeometry, features: gpd.GeoDataFrame) -> float:
    if features.empty:
        return float("inf")
    return features.geometry.distance(site).min()


def proximity_score(
    site: BaseGeometry,
    transit_nodes: gpd.GeoDataFrame,
    aeronautical_infrastructure: gpd.GeoDataFrame,
    major_roads: gpd.GeoDataFrame,
) -> ProximityBreakdown:
    """Combined [0, 1] proximity score. All inputs must share `site`'s projected CRS."""
    transit_score = _linear_decay_score(
        _nearest_distance(site, transit_nodes), TRANSIT_FAVORABLE_DISTANCE_M
    )
    aeronautical_score = _linear_decay_score(
        _nearest_distance(site, aeronautical_infrastructure), AERONAUTICAL_FAVORABLE_DISTANCE_M
    )
    road_score = _linear_decay_score(
        _nearest_distance(site, major_roads), ROAD_FAVORABLE_DISTANCE_M
    )
    combined = (
        _SUB_WEIGHTS["transit"] * transit_score
        + _SUB_WEIGHTS["aeronautical"] * aeronautical_score
        + _SUB_WEIGHTS["road"] * road_score
    )
    return ProximityBreakdown(
        transit_score=transit_score,
        aeronautical_score=aeronautical_score,
        road_score=road_score,
        combined_score=combined,
    )
