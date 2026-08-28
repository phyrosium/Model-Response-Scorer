"""Endpoint tests for rubric creation -- the constraint-backed paths that
Pydantic alone can't cover.
"""


def make_rubric(client, name, criteria=None):
    # `is None` rather than a truthiness check: an empty list is a case under
    # test, not a request for the default
    if criteria is None:
        criteria = [{"name": "Accuracy"}]
    return client.post("/rubrics", json={"name": name, "criteria": criteria})


def test_create_assigns_positions_from_list_order(client):
    r = make_rubric(
        client,
        "Ordered rubric",
        [{"name": "Third"}, {"name": "First"}, {"name": "Second"}],
    )
    assert r.status_code == 201
    criteria = r.json()["criteria"]
    assert [c["position"] for c in criteria] == [0, 1, 2]
    # order is preserved as sent, not sorted by name
    assert [c["name"] for c in criteria] == ["Third", "First", "Second"]


def test_duplicate_rubric_name_is_409(client):
    assert make_rubric(client, "Only one of these").status_code == 201
    second = make_rubric(client, "Only one of these")
    assert second.status_code == 409
    assert "already exists" in second.json()["detail"]


def test_failed_create_leaves_no_orphan_criteria(client, db):
    from models import RubricCriterion

    make_rubric(client, "Duplicate me", [{"name": "A"}, {"name": "B"}])
    before = db.query(RubricCriterion).count()

    assert make_rubric(client, "Duplicate me", [{"name": "C"}, {"name": "D"}]).status_code == 409

    assert db.query(RubricCriterion).count() == before
    assert db.query(RubricCriterion).filter_by(name="C").count() == 0


def test_duplicate_criterion_names_rejected_before_the_database(client):
    r = make_rubric(client, "Dupe criteria", [{"name": "A"}, {"name": "A"}])
    assert r.status_code == 422


def test_empty_criteria_rejected(client):
    assert make_rubric(client, "Empty", []).status_code == 422


def test_get_unknown_rubric_is_404(client):
    assert client.get("/rubrics/1000000000").status_code == 404


def test_created_rubric_is_readable_back(client):
    created = make_rubric(client, "Readable", [{"name": "A", "max_score": 7}]).json()
    fetched = client.get(f"/rubrics/{created['id']}").json()
    assert fetched["name"] == "Readable"
    assert fetched["criteria"][0]["max_score"] == 7
