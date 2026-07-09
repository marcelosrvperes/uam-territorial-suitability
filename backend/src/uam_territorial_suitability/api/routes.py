import os
from enum import Enum
from functools import lru_cache

import geopandas as gpd
from fastapi import APIRouter
from pydantic import BaseModel, Field
from shapely.geometry import Point

from uam_territorial_suitability.criteria import CRITERIA, Criterion
from uam_territorial_suitability.criteria_airspace import airspace_light_score
from uam_territorial_suitability.criteria_geometry import GeometryStandard, passes_geometry
from uam_territorial_suitability.data_sources import load_reh_corridors

router = APIRouter()

# Path to the REH corridors dataset (see data_sources.load_reh_corridors) for
# whatever municipality this deployment is configured for. Deliberately not
# hardcoded to any personal path — set per-deployment via environment
# variable so the tool stays usable by any municipality (D07).
_REH_CORRIDORS_PATH_ENV = "REH_CORRIDORS_PATH"


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


class AptitudeResponse(BaseModel):
    criteria: dict[str, CriterionOutcome]
    note: str


@router.post("/aptitude", response_model=AptitudeResponse)
def compute_aptitude(request: AptitudeRequest) -> AptitudeResponse:
    """Compute the criteria that are implemented so far for a candidate site.

    This does NOT yet return a final aggregated aptitude score — several
    criteria (obstacles, land_use, proximity, topography) still require
    raster/OSM data wiring (see 13-Camada2/STATUS.md, Gate G3). Each criterion
    in the response is explicitly marked computed vs. not_implemented so the
    caller never mistakes a partial evaluation for a complete one.
    """
    site_wgs84 = gpd.GeoSeries([Point(request.longitude, request.latitude)], crs="EPSG:4326")
    site = site_wgs84.to_crs("EPSG:31983").iloc[0]

    results: dict[str, CriterionOutcome] = {}

    geometry_ok = passes_geometry(
        available_diameter_m=request.available_diameter_m,
        standard=request.geometry_standard,
        aircraft_d_m=request.aircraft_d_m,
        aircraft_rd_m=request.aircraft_rd_m,
    )
    results["geometry"] = CriterionOutcome(status=CriterionStatus.COMPUTED, value=geometry_ok)

    reh_path = os.environ.get(_REH_CORRIDORS_PATH_ENV)
    if reh_path is None:
        results["airspace_light"] = CriterionOutcome(
            status=CriterionStatus.NOT_IMPLEMENTED,
            detail=f"Set the {_REH_CORRIDORS_PATH_ENV} environment variable to enable this criterion.",
        )
    else:
        reh = _cached_reh_corridors(reh_path)
        results["airspace_light"] = CriterionOutcome(
            status=CriterionStatus.COMPUTED, value=airspace_light_score(site, reh)
        )

    for criterion in CRITERIA:
        if criterion.id not in results:
            results[criterion.id] = CriterionOutcome(status=CriterionStatus.NOT_IMPLEMENTED)

    return AptitudeResponse(
        criteria=results,
        note=(
            "Resultado parcial — nem todos os critérios estão implementados ainda. "
            "Não use como score final de aptidão."
        ),
    )
