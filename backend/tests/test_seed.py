"""Tests for the starter-rubric seed.

Each test clears the rubrics table first. That is safe because the fixture wraps
everything in a transaction that is rolled back afterwards, so the real dev data
is untouched.
"""

from models import Rubric, RubricCriterion
from seed import STARTER_RUBRICS, seed


def empty_the_rubrics(db):
    for rubric in db.query(Rubric).all():
        db.delete(rubric)
    db.flush()


def test_seeds_a_fresh_database(db):
    empty_the_rubrics(db)

    assert seed(db) == len(STARTER_RUBRICS)
    assert db.query(Rubric).count() == len(STARTER_RUBRICS)


def test_does_nothing_when_rubrics_already_exist(db):
    """A second run must not duplicate, and must not resurrect a deleted one."""
    empty_the_rubrics(db)
    seed(db)

    before = db.query(Rubric).count()
    assert seed(db) == 0
    assert db.query(Rubric).count() == before


def test_a_deleted_starter_rubric_stays_deleted(db):
    empty_the_rubrics(db)
    seed(db)

    victim = db.query(Rubric).filter_by(name="Answer quality").one()
    db.delete(victim)
    db.flush()

    assert seed(db) == 0
    assert db.query(Rubric).filter_by(name="Answer quality").count() == 0


def test_criteria_are_created_with_positions_in_order(db):
    empty_the_rubrics(db)
    seed(db)

    for spec in STARTER_RUBRICS:
        rubric = db.query(Rubric).filter_by(name=spec["name"]).one()
        assert [c.position for c in rubric.criteria] == list(
            range(len(spec["criteria"]))
        )
        assert [c.name for c in rubric.criteria] == [
            c["name"] for c in spec["criteria"]
        ]


def test_seeded_rows_satisfy_the_same_constraints_as_user_rubrics(db):
    empty_the_rubrics(db)
    seed(db)

    for criterion in db.query(RubricCriterion).all():
        assert criterion.max_score > 0
        assert criterion.weight >= 0
        assert criterion.name


def test_seeded_rubrics_are_readable_through_the_api(client, db):
    empty_the_rubrics(db)
    seed(db)

    listed = client.get("/rubrics").json()
    names = {r["name"] for r in listed}
    assert {s["name"] for s in STARTER_RUBRICS} <= names


def test_a_seeded_rubric_can_be_scored_against(client, db, sample):
    """Nothing marks these rows as special, so scoring one works normally."""
    empty_the_rubrics(db)
    seed(db)

    rubric = db.query(Rubric).filter_by(name="Answer quality").one()
    criterion = rubric.criteria[0]

    r = client.post(
        "/scores",
        json={
            "response_id": sample.response.id,
            "criterion_id": criterion.id,
            "value": 4,
            "rationale": "scored against a seeded rubric",
        },
    )
    assert r.status_code == 200
    assert r.json()["criterion"]["name"] == criterion.name


def test_starter_rubric_names_are_unique(db):
    """The rubrics.name unique constraint would make a duplicate seed fail."""
    names = [s["name"] for s in STARTER_RUBRICS]
    assert len(names) == len(set(names))
