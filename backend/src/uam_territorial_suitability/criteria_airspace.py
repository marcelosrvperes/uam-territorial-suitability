"""Criterion 6 — Compatibilidade aeroespacial leve (weighted, D11/D17).

Deliberately shallow: presence/proximity to the REH (Rotas Especiais de
Helicóptero) network only. Full airspace/corridor engineering is out of scope
for this module (reserved for the future Módulo 05 — see D11). This is the
highest-weighted criterion in the AHP proposal (D29) despite being the
simplest to compute — weight and computational depth are independent axes,
see DECISIONS.md D29/D30.
"""

import geopandas as gpd
from shapely.geometry.base import BaseGeometry

# Beyond this distance from the nearest REH corridor, the score is 0 — treated
# as "no meaningful airspace integration benefit". Placeholder until a
# literature-grounded threshold is chosen (Gate G3 pendency, see
# criterios_aptidao.md criterion 6 — currently binary intersection only).
_MAX_FAVORABLE_DISTANCE_M = 2000.0


def distance_to_nearest_corridor(site: BaseGeometry, reh_corridors: gpd.GeoDataFrame) -> float:
    """Distance in meters from a candidate site to the nearest REH corridor polygon.

    Returns 0.0 if the site is inside a corridor. `reh_corridors` must already
    be in the same projected CRS as `site` (see data_sources.WORKING_CRS).
    """
    if reh_corridors.empty:
        return float("inf")
    return reh_corridors.geometry.distance(site).min()


def airspace_light_score(site: BaseGeometry, reh_corridors: gpd.GeoDataFrame) -> float:
    """Normalized [0, 1] score for the airspace-light criterion.

    1.0 = inside or touching a REH corridor; linearly decaying to 0.0 at
    `_MAX_FAVORABLE_DISTANCE_M`; 0.0 beyond that.
    """
    distance = distance_to_nearest_corridor(site, reh_corridors)
    if distance <= 0:
        return 1.0
    if distance >= _MAX_FAVORABLE_DISTANCE_M:
        return 0.0
    return 1.0 - (distance / _MAX_FAVORABLE_DISTANCE_M)
