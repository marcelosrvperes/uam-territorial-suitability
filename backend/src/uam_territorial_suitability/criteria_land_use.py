"""Criterion 4 — Uso do solo e compatibilidade de vizinhança (weighted, D24/D28).

Sources: Ison, D. (WSDOT Aviation Division), Vertiports Land Use
Compatibility Supplement (zones + P/L/X table) and Wei et al. (2023, Mineta
Transportation Institute, 500 ft sensitive-use buffer) — see
criterios_aptidao.md criterion 4.

Zone radii (converted from feet, Ison/WSDOT):
    Zone A: 200 ft  = 60.96 m   (overflight <=100 ft AGL, highest exposure)
    Zone B: 710 ft  = 216.41 m
    Zone C: 1000 ft = 304.80 m
    Buffer: 1551 ft = 472.74 m
"""

from enum import Enum

import geopandas as gpd
from pydantic import BaseModel
from shapely.geometry.base import BaseGeometry

_FT_TO_M = 0.3048


class Zone(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    BUFFER = "buffer"
    OUTSIDE = "outside"


ZONE_RADIUS_M: dict[Zone, float] = {
    Zone.A: 200 * _FT_TO_M,
    Zone.B: 710 * _FT_TO_M,
    Zone.C: 1000 * _FT_TO_M,
    Zone.BUFFER: 1551 * _FT_TO_M,
}

# Closer zones matter more — placeholder weighting pending literature
# grounding (same status as other normalizations, see metodo_agregacao.md).
_ZONE_IMPORTANCE: dict[Zone, float] = {
    Zone.A: 1.0,
    Zone.B: 0.7,
    Zone.C: 0.4,
    Zone.BUFFER: 0.2,
}


class Compatibility(str, Enum):
    PERMITTED = "P"
    LIMITED = "L"
    PROHIBITED = "X"


_COMPATIBILITY_VALUE: dict[Compatibility, float] = {
    Compatibility.PERMITTED: 1.0,
    Compatibility.LIMITED: 0.5,
    Compatibility.PROHIBITED: 0.0,
}

# Extract of the Ison/WSDOT compatibility table (criterios_aptidao.md
# criterion 4) — land-use category -> compatibility per zone. Categories are
# the tool's own vocabulary; OSM tags are mapped to them in `OSM_TAG_TO_CATEGORY`.
LAND_USE_COMPATIBILITY: dict[str, dict[Zone, Compatibility]] = {
    "residential": {
        Zone.A: Compatibility.PROHIBITED,
        Zone.B: Compatibility.PROHIBITED,
        Zone.C: Compatibility.LIMITED,
        Zone.BUFFER: Compatibility.LIMITED,
    },
    "school": {
        Zone.A: Compatibility.PROHIBITED,
        Zone.B: Compatibility.PROHIBITED,
        Zone.C: Compatibility.LIMITED,
        Zone.BUFFER: Compatibility.LIMITED,
    },
    "daycare": {
        Zone.A: Compatibility.PROHIBITED,
        Zone.B: Compatibility.PROHIBITED,
        Zone.C: Compatibility.PROHIBITED,
        Zone.BUFFER: Compatibility.PROHIBITED,
    },
    "hospital": {
        Zone.A: Compatibility.PROHIBITED,
        Zone.B: Compatibility.PROHIBITED,
        Zone.C: Compatibility.LIMITED,
        Zone.BUFFER: Compatibility.LIMITED,
    },
    "medical_clinic": {
        Zone.A: Compatibility.PROHIBITED,
        Zone.B: Compatibility.PROHIBITED,
        Zone.C: Compatibility.LIMITED,
        Zone.BUFFER: Compatibility.LIMITED,
    },
    "assisted_living": {
        Zone.A: Compatibility.PROHIBITED,
        Zone.B: Compatibility.PROHIBITED,
        Zone.C: Compatibility.PROHIBITED,
        Zone.BUFFER: Compatibility.LIMITED,
    },
    "power_infrastructure": {
        Zone.A: Compatibility.PROHIBITED,
        Zone.B: Compatibility.PERMITTED,
        Zone.C: Compatibility.PERMITTED,
        Zone.BUFFER: Compatibility.PERMITTED,
    },
    "communication_tower": {
        Zone.A: Compatibility.PROHIBITED,
        Zone.B: Compatibility.PROHIBITED,
        Zone.C: Compatibility.PERMITTED,
        Zone.BUFFER: Compatibility.PERMITTED,
    },
    "mixed_use_commercial_residential": {
        Zone.A: Compatibility.PROHIBITED,
        Zone.B: Compatibility.PERMITTED,
        Zone.C: Compatibility.PERMITTED,
        Zone.BUFFER: Compatibility.PERMITTED,
    },
}

# OpenStreetMap tag values -> this module's category vocabulary. Used by the
# (separate, network-dependent) OSM fetch helper — kept apart from the pure
# scoring logic below so the scoring function stays trivially testable.
OSM_TAG_TO_CATEGORY: dict[str, str] = {
    "school": "school",
    "kindergarten": "daycare",
    "hospital": "hospital",
    "clinic": "medical_clinic",
    "doctors": "medical_clinic",
    "social_facility": "assisted_living",
}


class WorstFinding(BaseModel):
    category: str
    zone: Zone
    compatibility: Compatibility
    distance_m: float
    score: float


def classify_zone(distance_m: float) -> Zone:
    if distance_m <= ZONE_RADIUS_M[Zone.A]:
        return Zone.A
    if distance_m <= ZONE_RADIUS_M[Zone.B]:
        return Zone.B
    if distance_m <= ZONE_RADIUS_M[Zone.C]:
        return Zone.C
    if distance_m <= ZONE_RADIUS_M[Zone.BUFFER]:
        return Zone.BUFFER
    return Zone.OUTSIDE


def land_use_score(
    site: BaseGeometry,
    land_use_features: gpd.GeoDataFrame,
    category_column: str = "category",
) -> tuple[float, WorstFinding | None]:
    """Land-use compatibility score in [0, 1] for a candidate site.

    `land_use_features` must be in the same projected CRS as `site` and have
    a column (default "category") with values from
    `LAND_USE_COMPATIBILITY`/`OSM_TAG_TO_CATEGORY`. Unknown categories are
    ignored (treated as not present in the compatibility table, not as a
    penalty — avoids silently punishing sites for OSM tags we don't map yet).

    Returns (score, worst_finding) — worst_finding is None when no relevant
    feature was found within the Buffer zone (score defaults to 1.0, i.e. no
    known conflict — not proof of compatibility, just absence of evidence).
    """
    worst_finding: WorstFinding | None = None

    for _, row in land_use_features.iterrows():
        category = row.get(category_column)
        if category not in LAND_USE_COMPATIBILITY:
            continue
        distance = site.distance(row.geometry)
        zone = classify_zone(distance)
        if zone is Zone.OUTSIDE:
            continue
        compatibility = LAND_USE_COMPATIBILITY[category][zone]
        candidate_score = 1.0 - _ZONE_IMPORTANCE[zone] * (1.0 - _COMPATIBILITY_VALUE[compatibility])
        # <= (not <): a feature must be recorded as the "worst finding" even
        # when it is fully permitted (score 1.0), so the caller always knows
        # *why* the score came out the way it did instead of only seeing "no
        # data" — see test_power_infrastructure_in_zone_b_is_permitted.
        if worst_finding is None or candidate_score <= worst_finding.score:
            worst_finding = WorstFinding(
                category=category,
                zone=zone,
                compatibility=compatibility,
                distance_m=distance,
                score=candidate_score,
            )

    if worst_finding is None:
        return 1.0, None
    return worst_finding.score, worst_finding
