import pytest

from uam_territorial_suitability.aggregation import (
    WEIGHTS,
    aggregate_score,
    evaluate_exclusion,
    evaluate_site,
)


def test_weights_sum_to_one() -> None:
    assert sum(WEIGHTS.values()) == pytest.approx(1.0, abs=1e-3)


def test_evaluate_exclusion_all_pass() -> None:
    result = evaluate_exclusion({"geometry": True, "topography": True})
    assert result.passed
    assert result.failed_criteria == []


def test_evaluate_exclusion_one_fails() -> None:
    result = evaluate_exclusion({"geometry": True, "topography": False})
    assert not result.passed
    assert result.failed_criteria == ["topography"]


def test_aggregate_score_perfect_site() -> None:
    scores = {cid: 1.0 for cid in WEIGHTS}
    assert aggregate_score(scores) == pytest.approx(1.0, abs=1e-6)


def test_aggregate_score_worst_site() -> None:
    scores = {cid: 0.0 for cid in WEIGHTS}
    assert aggregate_score(scores) == pytest.approx(0.0, abs=1e-6)


def test_aggregate_score_missing_criterion_defaults_to_zero() -> None:
    # Only supplying one of the four weighted criteria — the rest must count as 0,
    # not be silently dropped from the weighted sum.
    scores = {"airspace_light": 1.0}
    assert aggregate_score(scores) == pytest.approx(WEIGHTS["airspace_light"], abs=1e-6)


def test_evaluate_site_excluded_has_no_score() -> None:
    result = evaluate_site(
        exclusion_pass={"geometry": False},
        weighted_scores={cid: 1.0 for cid in WEIGHTS},
    )
    assert result.excluded
    assert result.score is None
    assert result.failed_criteria == ["geometry"]


def test_evaluate_site_passed_has_score() -> None:
    result = evaluate_site(
        exclusion_pass={"geometry": True, "topography": True},
        weighted_scores={cid: 0.5 for cid in WEIGHTS},
    )
    assert not result.excluded
    assert result.score == pytest.approx(0.5, abs=1e-6)
    assert result.criterion_scores is not None
