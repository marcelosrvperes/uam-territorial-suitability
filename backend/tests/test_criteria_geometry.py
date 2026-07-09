import pytest

from uam_territorial_suitability.criteria_geometry import (
    GeometryStandard,
    passes_geometry,
    required_areas,
)

# Reference values from 13-Camada2/04-metodologia/criterios_aptidao.md, criterion 1,
# hypothesis D = RD = 16.00 m (matches the sandbox F1-T04 comparison, D21).


def test_faa_required_areas_match_methodology() -> None:
    areas = required_areas(GeometryStandard.FAA, aircraft_d_m=16.0, aircraft_rd_m=16.0)
    assert areas.tlof_m == pytest.approx(16.0)
    assert areas.fato_m == pytest.approx(32.0)
    assert areas.safety_area_m == pytest.approx(40.0)


def test_easa_required_areas_match_methodology() -> None:
    areas = required_areas(GeometryStandard.EASA, aircraft_d_m=16.0)
    assert areas.tlof_m == pytest.approx(13.28)
    assert areas.fato_m == pytest.approx(24.0)
    assert areas.safety_area_m == pytest.approx(32.0)


def test_rd_defaults_to_d_when_not_supplied() -> None:
    with_rd = required_areas(GeometryStandard.FAA, aircraft_d_m=16.0, aircraft_rd_m=16.0)
    without_rd = required_areas(GeometryStandard.FAA, aircraft_d_m=16.0)
    assert with_rd == without_rd


def test_passes_geometry_true_when_site_large_enough() -> None:
    assert passes_geometry(available_diameter_m=45.0, standard=GeometryStandard.EASA, aircraft_d_m=16.0)


def test_passes_geometry_false_when_site_too_small() -> None:
    assert not passes_geometry(
        available_diameter_m=20.0, standard=GeometryStandard.FAA, aircraft_d_m=16.0
    )


def test_faa_more_conservative_than_easa_for_same_aircraft() -> None:
    # Cross-check against the methodology's own finding (D21 discussion): FAA
    # demands a larger clear area than EASA for the same reference aircraft.
    faa = required_areas(GeometryStandard.FAA, aircraft_d_m=16.0, aircraft_rd_m=16.0)
    easa = required_areas(GeometryStandard.EASA, aircraft_d_m=16.0)
    assert faa.safety_area_m > easa.safety_area_m


def test_invalid_aircraft_dimension_raises() -> None:
    with pytest.raises(ValueError):
        required_areas(GeometryStandard.FAA, aircraft_d_m=0)
