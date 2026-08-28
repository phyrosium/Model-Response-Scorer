"""Endpoint tests for scoring, against a real database inside a rolled-back
transaction. These cover the paths Pydantic cannot: the per-criterion ceiling,
the 404s, and the upsert.
"""


def post_score(client, response_id, criterion_id, value, rationale=None):
    return client.post(
        "/scores",
        json={
            "response_id": response_id,
            "criterion_id": criterion_id,
            "value": value,
            "rationale": rationale,
        },
    )


class TestCeiling:
    """scores.value has no upper bound in the database -- max_score lives on
    another table -- so this check exists only in the endpoint."""

    def test_value_above_criterion_max_is_rejected(self, client, sample):
        r = post_score(client, sample.response.id, sample.concision.id, 99)
        assert r.status_code == 422
        assert "exceeds max_score 3" in r.json()["detail"]
        assert "Concision" in r.json()["detail"]

    def test_one_over_the_ceiling_is_rejected(self, client, sample):
        r = post_score(client, sample.response.id, sample.concision.id, 4)
        assert r.status_code == 422

    def test_exactly_at_the_ceiling_is_accepted(self, client, sample):
        r = post_score(client, sample.response.id, sample.concision.id, 3)
        assert r.status_code == 200
        assert r.json()["value"] == 3

    def test_ceiling_is_per_criterion_not_global(self, client, sample):
        """4 is legal on the 5-point criterion and illegal on the 3-point one."""
        assert post_score(client, sample.response.id, sample.accuracy.id, 4).status_code == 200
        assert post_score(client, sample.response.id, sample.concision.id, 4).status_code == 422

    def test_negative_value_rejected_by_schema(self, client, sample):
        assert post_score(client, sample.response.id, sample.accuracy.id, -1).status_code == 422


class TestUpsert:
    def test_first_submission_creates(self, client, sample):
        r = post_score(client, sample.response.id, sample.accuracy.id, 5, "Good.")
        assert r.status_code == 200
        assert r.json()["value"] == 5
        assert r.json()["rationale"] == "Good."

    def test_resubmitting_the_same_cell_updates_in_place(self, client, sample):
        first = post_score(client, sample.response.id, sample.accuracy.id, 5, "Good.")
        second = post_score(client, sample.response.id, sample.accuracy.id, 2, "Changed my mind.")

        assert second.status_code == 200
        # same row, not a duplicate
        assert second.json()["id"] == first.json()["id"]
        assert second.json()["value"] == 2
        assert second.json()["rationale"] == "Changed my mind."

        listed = client.get(f"/responses/{sample.response.id}/scores").json()
        assert len(listed) == 1

    def test_resubmitting_can_clear_the_rationale(self, client, sample):
        post_score(client, sample.response.id, sample.accuracy.id, 5, "Had a reason.")
        second = post_score(client, sample.response.id, sample.accuracy.id, 5)
        assert second.json()["rationale"] is None

    def test_score_is_always_tagged_manual(self, client, sample):
        r = post_score(client, sample.response.id, sample.accuracy.id, 5)
        assert r.json()["source"] == "manual"

    def test_client_cannot_claim_an_auto_score(self, client, sample):
        r = client.post(
            "/scores",
            json={
                "response_id": sample.response.id,
                "criterion_id": sample.accuracy.id,
                "value": 5,
                "source": "auto",
            },
        )
        assert r.json()["source"] == "manual"


class TestNotFound:
    def test_unknown_response_is_404(self, client, sample):
        r = post_score(client, 10**9, sample.accuracy.id, 1)
        assert r.status_code == 404
        assert "response" in r.json()["detail"]

    def test_unknown_criterion_is_404(self, client, sample):
        r = post_score(client, sample.response.id, 10**9, 1)
        assert r.status_code == 404
        assert "criterion" in r.json()["detail"]

    def test_listing_scores_for_unknown_response_is_404(self, client):
        assert client.get("/responses/1000000000/scores").status_code == 404


class TestListing:
    def test_unscored_response_returns_empty_list_not_404(self, client, sample):
        r = client.get(f"/responses/{sample.unscored.id}/scores")
        assert r.status_code == 200
        assert r.json() == []

    def test_scores_come_back_in_criterion_position_order(self, client, sample):
        # deliberately score the second criterion first
        post_score(client, sample.response.id, sample.concision.id, 3)
        post_score(client, sample.response.id, sample.accuracy.id, 5)

        names = [s["criterion"]["name"] for s in client.get(
            f"/responses/{sample.response.id}/scores").json()]
        assert names == ["Accuracy", "Concision"]

    def test_criterion_detail_is_embedded(self, client, sample):
        post_score(client, sample.response.id, sample.concision.id, 2)
        criterion = client.get(f"/responses/{sample.response.id}/scores").json()[0]["criterion"]
        assert criterion["name"] == "Concision"
        assert criterion["max_score"] == 3
        assert criterion["weight"] == 1.0
