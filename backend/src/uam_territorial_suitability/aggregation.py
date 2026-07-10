"""AHP-based aggregation of territorial aptitude criteria.

Two-stage structure (see 13-Camada2/04-metodologia/metodo_agregacao.md, D25):
  1. Binary exclusion filters (geometry, heliport_retrofit) — a site failing
     any of these is discarded outright, no partial credit. Topography was
     dropped from this module's exclusion set (D53) — out of scope now.
  2. Weighted aggregation (AHP) of the continuous criteria (obstacles, land_use,
     proximity, airspace_light) for sites that pass stage 1.

Weights are the initial proposal from D29 (mapped from Mercan et al. 2025, BWM).
"""

from pydantic import BaseModel

from uam_territorial_suitability.criteria import CRITERIA, CriterionKind

WEIGHTED_CRITERIA_IDS = [c.id for c in CRITERIA if c.kind == CriterionKind.WEIGHTED]
WEIGHTS: dict[str, float] = {c.id: c.weight for c in CRITERIA if c.weight is not None}

_WEIGHT_SUM_TOLERANCE = 1e-6


def _validate_weights() -> None:
    total = sum(WEIGHTS.values())
    if abs(total - 1.0) > 1e-3:
        raise ValueError(f"AHP weights must sum to 1.0, got {total:.6f}: {WEIGHTS}")


_validate_weights()


class ExclusionResult(BaseModel):
    """Result of the binary exclusion stage for one candidate site."""

    passed: bool
    failed_criteria: list[str]


class AptitudeResult(BaseModel):
    """Final aptitude result for one candidate site."""

    excluded: bool
    failed_criteria: list[str]
    score: float | None = None  # None when excluded
    criterion_scores: dict[str, float] | None = None


def evaluate_exclusion(exclusion_pass: dict[str, bool]) -> ExclusionResult:
    """Combine binary exclusion criteria into a single pass/fail result.

    `exclusion_pass` maps criterion id -> True (site passes that criterion) /
    False (site fails it). Missing exclusion criteria are treated as not
    evaluated and do not block the site (caller's responsibility to supply all
    relevant ones).
    """
    failed = [criterion_id for criterion_id, passed in exclusion_pass.items() if not passed]
    return ExclusionResult(passed=len(failed) == 0, failed_criteria=failed)


def aggregate_score(criterion_scores: dict[str, float]) -> float:
    """Weighted sum of the continuous (weighted) criteria for one site.

    Each score in `criterion_scores` must be normalized to [0, 1], where 1 is
    the most favorable outcome for that criterion. Missing weighted criteria
    default to 0 (least favorable) rather than being silently excluded from
    the sum, so an incomplete evaluation is never scored as if it were good.
    """
    return sum(WEIGHTS[cid] * criterion_scores.get(cid, 0.0) for cid in WEIGHTED_CRITERIA_IDS)


def evaluate_site(
    exclusion_pass: dict[str, bool],
    weighted_scores: dict[str, float],
) -> AptitudeResult:
    """Full two-stage evaluation for one candidate site."""
    exclusion = evaluate_exclusion(exclusion_pass)
    if not exclusion.passed:
        return AptitudeResult(excluded=True, failed_criteria=exclusion.failed_criteria)

    score = aggregate_score(weighted_scores)
    return AptitudeResult(
        excluded=False,
        failed_criteria=[],
        score=score,
        criterion_scores={cid: weighted_scores.get(cid, 0.0) for cid in WEIGHTED_CRITERIA_IDS},
    )
