from enum import Enum
from functools import lru_cache

import geopandas as gpd
import requests
from fastapi import APIRouter
from pydantic import BaseModel, Field
from shapely.geometry import Point

from uam_territorial_suitability import settings
from uam_territorial_suitability.aggregation import evaluate_site
from uam_territorial_suitability.criteria import CRITERIA, Criterion
from uam_territorial_suitability.criteria_airspace import airspace_light_score
from uam_territorial_suitability.criteria_geometry import GeometryStandard, passes_geometry
from uam_territorial_suitability.criteria_land_use import ZONE_RADIUS_M, Zone, land_use_score
from uam_territorial_suitability.criteria_obstacles import find_ofv_violations, obstacles_score
from uam_territorial_suitability.criteria_topography import mean_slope_percent, passes_topography
from uam_territorial_suitability.data_sources import load_reh_corridors
from uam_territorial_suitability.osm_fetch import fetch_land_use_features

router = APIRouter()


@lru_cache(maxsize=1)
def _cached_reh_corridors(path: str) -> gpd.GeoDataFrame:
    return load_reh_corridors(path)


@router.get("/criteria", response_model=list[Criterion])
def list_criteria() -> list[Criterion]:
    """Return the territorial aptitude criteria currently defined for the tool."""
    return CRITERIA


class CriterionStatus(str, Enum):
    COMPUTED = "computed"
    NOT_IMPLEMENTED = "not_implemented"
    FAILED = "failed"  # data source configured but the computation errored (e.g. network)


class CriterionOutcome(BaseModel):
    status: CriterionStatus
    value: float | bool | None = None
    detail: str | None = None


class AptitudeRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    available_diameter_m: float = Field(gt=0)
    aircraft_d_m: float = Field(default=16.0, gt=0)
    aircraft_rd_m: float | None = Field(default=None, gt=0)
    geometry_standard: GeometryStandard = GeometryStandard.EASA
    reference_elevation_m: float | None = Field(
        default=None, description="Site ground elevation, needed for the obstacles criterion."
    )
    elevated_heliport: bool = Field(
        default=False, description="Whether the site is an elevated (rooftop/structure) heliport."
    )


class AptitudeResponse(BaseModel):
    criteria: dict[str, CriterionOutcome]
    aptitude: float | None = None
    excluded: bool | None = None
    note: str


@router.post("/aptitude", response_model=AptitudeResponse)
def compute_aptitude(request: AptitudeRequest) -> AptitudeResponse:
    """Compute territorial aptitude for a candidate site.

    Every criterion is computed if (and only if) its data source is
    configured for this deployment (see settings.py) and the computation
    succeeds; otherwise it is reported as not_implemented/failed rather than
    silently defaulting to a value. The final AHP-aggregated `aptitude`
    score (see aggregation.py) is only returned once every criterion needed
    for it — exclusion filters and weighted criteria alike — was actually
    computed; otherwise it stays None so a partial evaluation is never
    mistaken for a complete one.
    """
    site_wgs84 = gpd.GeoSeries([Point(request.longitude, request.latitude)], crs="EPSG:4326")
    site = site_wgs84.to_crs("EPSG:31983").iloc[0]

    results: dict[str, CriterionOutcome] = {}

    # --- geometry (exclusion) ---
    geometry_ok = passes_geometry(
        available_diameter_m=request.available_diameter_m,
        standard=request.geometry_standard,
        aircraft_d_m=request.aircraft_d_m,
        aircraft_rd_m=request.aircraft_rd_m,
    )
    results["geometry"] = CriterionOutcome(status=CriterionStatus.COMPUTED, value=geometry_ok)

    # --- airspace_light (weighted) ---
    reh_path = settings.reh_corridors_path()
    if reh_path is None:
        results["airspace_light"] = CriterionOutcome(
            status=CriterionStatus.NOT_IMPLEMENTED, detail="REH_CORRIDORS_PATH not configured."
        )
    else:
        reh = _cached_reh_corridors(reh_path)
        results["airspace_light"] = CriterionOutcome(
            status=CriterionStatus.COMPUTED, value=airspace_light_score(site, reh)
        )

    # --- topography (exclusion) ---
    dtm_path = settings.dtm_path()
    if dtm_path is None:
        results["topography"] = CriterionOutcome(
            status=CriterionStatus.NOT_IMPLEMENTED, detail="DTM_PATH not configured."
        )
    else:
        try:
            slope = mean_slope_percent(
                dtm_path, center_x=site.x, center_y=site.y,
                radius_m=request.available_diameter_m / 2,
            )
            results["topography"] = CriterionOutcome(
                status=CriterionStatus.COMPUTED,
                value=passes_topography(slope, elevated=request.elevated_heliport),
            )
        except ValueError as exc:
            results["topography"] = CriterionOutcome(status=CriterionStatus.FAILED, detail=str(exc))

    # --- obstacles (weighted) — near-site OFV path only (D36) ---
    dsm_path = settings.dsm_path()
    if dsm_path is None:
        results["obstacles"] = CriterionOutcome(
            status=CriterionStatus.NOT_IMPLEMENTED, detail="DSM_PATH not configured."
        )
    elif request.reference_elevation_m is None:
        results["obstacles"] = CriterionOutcome(
            status=CriterionStatus.NOT_IMPLEMENTED, detail="reference_elevation_m not supplied."
        )
    else:
        try:
            violations = find_ofv_violations(
                dsm_path, center_x=site.x, center_y=site.y,
                reference_elevation_m=request.reference_elevation_m,
                aircraft_d_m=request.aircraft_d_m,
            )
            results["obstacles"] = CriterionOutcome(
                status=CriterionStatus.COMPUTED, value=obstacles_score(violations)
            )
        except ValueError as exc:
            results["obstacles"] = CriterionOutcome(status=CriterionStatus.FAILED, detail=str(exc))

    # --- land_use (weighted) — live OSM query, no config needed (D19) ---
    try:
        features = fetch_land_use_features(
            lat=request.latitude, lon=request.longitude, radius_m=ZONE_RADIUS_M[Zone.BUFFER]
        )
        features_utm = features.to_crs("EPSG:31983") if not features.empty else features
        score, finding = land_use_score(site, features_utm)
        results["land_use"] = CriterionOutcome(
            status=CriterionStatus.COMPUTED,
            value=score,
            detail=f"Worst finding: {finding.category} in zone {finding.zone.value}" if finding else None,
        )
    except requests.RequestException as exc:
        results["land_use"] = CriterionOutcome(status=CriterionStatus.FAILED, detail=str(exc))

    # --- proximity (weighted) — not wired yet, needs a transit/road OSM fetcher ---
    results["proximity"] = CriterionOutcome(
        status=CriterionStatus.NOT_IMPLEMENTED,
        detail="Transit/road data source not wired into the API yet.",
    )

    # --- heliport_retrofit (exclusion) — composite of geometry + obstacles ---
    if results["geometry"].status == CriterionStatus.COMPUTED and results["obstacles"].status == CriterionStatus.COMPUTED:
        results["heliport_retrofit"] = CriterionOutcome(
            status=CriterionStatus.COMPUTED,
            value=bool(results["geometry"].value) and results["obstacles"].value == 1.0,
        )
    else:
        results["heliport_retrofit"] = CriterionOutcome(
            status=CriterionStatus.NOT_IMPLEMENTED,
            detail="Requires both geometry and obstacles to be computed first.",
        )

    for criterion in CRITERIA:
        if criterion.id not in results:
            results[criterion.id] = CriterionOutcome(status=CriterionStatus.NOT_IMPLEMENTED)

    aptitude: float | None = None
    excluded: bool | None = None
    all_computed = all(outcome.status == CriterionStatus.COMPUTED for outcome in results.values())
    if all_computed:
        exclusion_pass = {
            cid: bool(results[cid].value) for cid in ["geometry", "heliport_retrofit", "topography"]
        }
        weighted_scores = {
            cid: float(results[cid].value)
            for cid in ["obstacles", "land_use", "proximity", "airspace_light"]
        }
        outcome = evaluate_site(exclusion_pass, weighted_scores)
        excluded = outcome.excluded
        aptitude = outcome.score

    return AptitudeResponse(
        criteria=results,
        aptitude=aptitude,
        excluded=excluded,
        note=(
            "Score final de aptidão calculado."
            if aptitude is not None
            else "Resultado parcial — nem todos os critérios foram computados. "
            "Não use como score final de aptidão."
        ),
    )
