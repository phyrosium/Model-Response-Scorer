"""Validation tests for the rubric payloads.

These are pure Pydantic -- no database. The point is that a malformed rubric is
rejected at the edge with a 422 rather than reaching Postgres and coming back as
a 500 from a check or unique constraint.
"""

import pytest
from pydantic import ValidationError

from schemas import RubricCreate


def valid(**overrides):
    payload = {"name": "Answer quality", "criteria": [{"name": "Accuracy"}]}
    payload.update(overrides)
    return payload


def test_defaults_are_applied():
    rubric = RubricCreate(**valid())
    criterion = rubric.criteria[0]
    assert criterion.max_score == 5
    assert criterion.weight == 1.0
    assert criterion.description is None


def test_duplicate_criterion_names_rejected():
    with pytest.raises(ValidationError) as exc:
        RubricCreate(**valid(criteria=[{"name": "Accuracy"}, {"name": "Accuracy"}]))
    assert "duplicate criterion names" in str(exc.value)


def test_distinct_names_accepted():
    rubric = RubricCreate(**valid(criteria=[{"name": "Accuracy"}, {"name": "Tone"}]))
    assert [c.name for c in rubric.criteria] == ["Accuracy", "Tone"]


def test_empty_criteria_rejected():
    """A rubric with no criteria could never be scored against."""
    with pytest.raises(ValidationError):
        RubricCreate(**valid(criteria=[]))


@pytest.mark.parametrize("max_score", [0, -1])
def test_non_positive_max_score_rejected(max_score):
    """Mirrors the ck_criterion_max_score_positive constraint."""
    with pytest.raises(ValidationError):
        RubricCreate(**valid(criteria=[{"name": "A", "max_score": max_score}]))


def test_negative_weight_rejected():
    """Mirrors the ck_criterion_weight_non_negative constraint."""
    with pytest.raises(ValidationError):
        RubricCreate(**valid(criteria=[{"name": "A", "weight": -0.5}]))


def test_zero_weight_allowed():
    """Weight 0 is legal -- it means the criterion is scored but not counted."""
    rubric = RubricCreate(**valid(criteria=[{"name": "A", "weight": 0}]))
    assert rubric.criteria[0].weight == 0


def test_blank_rubric_name_rejected():
    with pytest.raises(ValidationError):
        RubricCreate(**valid(name=""))
