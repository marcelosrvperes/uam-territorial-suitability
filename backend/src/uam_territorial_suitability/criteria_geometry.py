"""Criterion 1 — Geometria e dimensões mínimas (exclusion filter).

Sources (see 13-Camada2/04-metodologia/criterios_aptidao.md, criterion 1 / D21 / D26):
    FAA, Engineering Brief No. 105A — Vertiport Design (2024)
    EASA, Prototype Technical Specifications for VFR Vertiports (PTS-VPT-DSN, 2022)

Both standards are kept as configurable options (D26) — the tool does not force
a single normative choice.
"""

from enum import Enum

from pydantic import BaseModel


class GeometryStandard(str, Enum):
    FAA = "faa"
    EASA = "easa"


class RequiredAreas(BaseModel):
    tlof_m: float
    fato_m: float
    safety_area_m: float


def required_areas(
    standard: GeometryStandard,
    aircraft_d_m: float,
    aircraft_rd_m: float | None = None,
) -> RequiredAreas:
    """Minimum TLOF/FATO/safety-area diameters for the given reference aircraft.

    `aircraft_d_m` is D (largest-dimension circle). `aircraft_rd_m` is RD
    (rotor/propeller reference circle, FAA-only) — defaults to `aircraft_d_m`
    when not supplied, matching the conservative hypothesis already used in
    the thesis methodology (D=RD) for aircraft without certified RD data.
    """
    if aircraft_d_m <= 0:
        raise ValueError("aircraft_d_m must be positive")

    rd = aircraft_rd_m if aircraft_rd_m is not None else aircraft_d_m

    if standard is GeometryStandard.FAA:
        tlof = 1.0 * rd
        fato = 2.0 * rd
        safety_area = 2.5 * aircraft_d_m
    else:  # EASA
        tlof = 0.83 * aircraft_d_m
        fato = 1.5 * aircraft_d_m
        safety_area = fato + 2.0 * max(3.0, 0.25 * aircraft_d_m)

    return RequiredAreas(tlof_m=tlof, fato_m=fato, safety_area_m=safety_area)


def passes_geometry(
    available_diameter_m: float,
    standard: GeometryStandard,
    aircraft_d_m: float,
    aircraft_rd_m: float | None = None,
) -> bool:
    """Whether a candidate site's available clear diameter fits the safety area.

    The safety area is the binding constraint (it is, by construction, the
    largest of the three required areas in both standards), so passing it
    implies TLOF and FATO also fit.
    """
    areas = required_areas(standard, aircraft_d_m, aircraft_rd_m)
    return available_diameter_m >= areas.safety_area_m
