"""Tests for the LLM judge.

The judge itself is stubbed. What is under test is everything around it: the
all-or-nothing validation of a verdict, and that a bad verdict leaves no scores
behind. A half-stored verdict would leave the comparison view quietly wrong,
which is worse than a visible failure.
"""

import pytest

import llm
from llm import GenerationError, JudgeCriterion, validate_verdict
from models import Score


def criteria():
    return [
        JudgeCriterion(id=1, name="Accuracy", description=None, max_score=5),
        JudgeCriterion(id=2, name="Concision", description=None, max_score=3),
    ]


def verdict(criterion_id, value, rationale="because"):
    return llm._CriterionVerdict(
        criterion_id=criterion_id, value=value, rationale=rationale
    )


class TestVerdictValidation:
    def test_a_complete_in_range_verdict_passes(self):
        scores = [verdict(1, 5), verdict(2, 3)]
        assert validate_verdict(scores, criteria()) == scores

    def test_zero_is_a_legal_judge_score(self):
        scores = [verdict(1, 0), verdict(2, 0)]
        assert validate_verdict(scores, criteria()) == scores

    def test_skipped_criterion_is_rejected(self):
        with pytest.raises(GenerationError) as exc:
            validate_verdict([verdict(1, 5)], criteria())
        assert exc.value.status_code == 502
        # names the criterion, not just its id
        assert "Concision" in exc.value.message

    def test_invented_criterion_id_is_rejected(self):
        with pytest.raises(GenerationError) as exc:
            validate_verdict([verdict(1, 5), verdict(2, 3), verdict(99, 1)], criteria())
        assert "invented" in exc.value.message
        assert "99" in exc.value.message

    def test_double_scoring_one_criterion_is_rejected(self):
        with pytest.raises(GenerationError) as exc:
            validate_verdict([verdict(1, 5), verdict(1, 2), verdict(2, 3)], criteria())
        assert "more than once" in exc.value.message

    def test_value_above_that_criterion_max_is_rejected(self):
        """The ceiling is per-criterion: 4 is fine on Accuracy, not on Concision."""
        validate_verdict([verdict(1, 4), verdict(2, 3)], criteria())
        with pytest.raises(GenerationError) as exc:
            validate_verdict([verdict(1, 4), verdict(2, 4)], criteria())
        assert "Concision" in exc.value.message
        assert "0-3" in exc.value.message

    def test_negative_value_is_rejected(self):
        with pytest.raises(GenerationError):
            validate_verdict([verdict(1, -1), verdict(2, 3)], criteria())


class TestAutoScoreEndpoint:
    def stub_judge(self, monkeypatch, result=None, raises=None):
        captured = {}

        def fake(prompt_text, response_text, criteria, model):
            captured.update(
                prompt_text=prompt_text,
                response_text=response_text,
                criteria=criteria,
                model=model,
            )
            if raises is not None:
                raise raises
            return result

        monkeypatch.setattr(llm, "judge", fake)
        return captured

    def test_writes_one_auto_score_per_criterion(self, client, sample, monkeypatch):
        self.stub_judge(
            monkeypatch,
            result=[
                verdict(sample.accuracy.id, 4, "solid"),
                verdict(sample.concision.id, 2, "a bit long"),
            ],
        )
        r = client.post(
            "/auto-score",
            json={"response_id": sample.response.id, "rubric_id": sample.rubric.id},
        )
        assert r.status_code == 201
        body = r.json()
        assert len(body) == 2
        assert {s["source"] for s in body} == {"auto"}
        assert {s["criterion"]["name"]: s["value"] for s in body} == {
            "Accuracy": 4,
            "Concision": 2,
        }

    def test_auto_scores_sit_alongside_manual_ones(self, client, sample, monkeypatch):
        client.post(
            "/scores",
            json={
                "response_id": sample.response.id,
                "criterion_id": sample.accuracy.id,
                "value": 5,
                "rationale": "human says 5",
            },
        )
        self.stub_judge(
            monkeypatch,
            result=[
                verdict(sample.accuracy.id, 2, "judge says 2"),
                verdict(sample.concision.id, 3),
            ],
        )
        client.post(
            "/auto-score",
            json={"response_id": sample.response.id, "rubric_id": sample.rubric.id},
        )

        listed = client.get(f"/responses/{sample.response.id}/scores").json()
        accuracy = [s for s in listed if s["criterion"]["name"] == "Accuracy"]
        assert {s["source"]: s["value"] for s in accuracy} == {"manual": 5, "auto": 2}

    def test_rerunning_updates_rather_than_duplicating(self, client, sample, monkeypatch):
        self.stub_judge(
            monkeypatch,
            result=[verdict(sample.accuracy.id, 1), verdict(sample.concision.id, 1)],
        )
        first = client.post(
            "/auto-score",
            json={"response_id": sample.response.id, "rubric_id": sample.rubric.id},
        ).json()

        self.stub_judge(
            monkeypatch,
            result=[verdict(sample.accuracy.id, 5), verdict(sample.concision.id, 3)],
        )
        second = client.post(
            "/auto-score",
            json={"response_id": sample.response.id, "rubric_id": sample.rubric.id},
        ).json()

        assert {s["id"] for s in first} == {s["id"] for s in second}
        assert sorted(s["value"] for s in second) == [3, 5]
        assert len(client.get(f"/responses/{sample.response.id}/scores").json()) == 2

    def test_the_judge_is_not_shown_existing_manual_scores(
        self, client, sample, monkeypatch
    ):
        """Anchoring the judge to the human's numbers would void the comparison."""
        client.post(
            "/scores",
            json={
                "response_id": sample.response.id,
                "criterion_id": sample.accuracy.id,
                "value": 5,
                "rationale": "an extremely distinctive human rationale",
            },
        )
        captured = self.stub_judge(
            monkeypatch,
            result=[verdict(sample.accuracy.id, 1), verdict(sample.concision.id, 1)],
        )
        client.post(
            "/auto-score",
            json={"response_id": sample.response.id, "rubric_id": sample.rubric.id},
        )

        everything_sent = f"{captured['prompt_text']} {captured['response_text']}"
        assert "distinctive human rationale" not in everything_sent
        assert not hasattr(captured["criteria"][0], "value")

    def test_a_rejected_verdict_writes_nothing(self, client, sample, monkeypatch):
        self.stub_judge(
            monkeypatch,
            raises=GenerationError("The judge skipped criteria: ['Concision']", 502),
        )
        r = client.post(
            "/auto-score",
            json={"response_id": sample.response.id, "rubric_id": sample.rubric.id},
        )
        assert r.status_code == 502
        assert client.get(f"/responses/{sample.response.id}/scores").json() == []

    def test_unknown_response_is_404(self, client, sample, monkeypatch):
        self.stub_judge(monkeypatch, result=[])
        r = client.post(
            "/auto-score", json={"response_id": 10**9, "rubric_id": sample.rubric.id}
        )
        assert r.status_code == 404
        assert "response" in r.json()["detail"]

    def test_unknown_rubric_is_404(self, client, sample, monkeypatch):
        self.stub_judge(monkeypatch, result=[])
        r = client.post(
            "/auto-score",
            json={"response_id": sample.response.id, "rubric_id": 10**9},
        )
        assert r.status_code == 404
        assert "rubric" in r.json()["detail"]

    def test_the_judge_sees_the_original_prompt_and_the_response(
        self, client, sample, monkeypatch
    ):
        captured = self.stub_judge(
            monkeypatch,
            result=[verdict(sample.accuracy.id, 1), verdict(sample.concision.id, 1)],
        )
        client.post(
            "/auto-score",
            json={"response_id": sample.response.id, "rubric_id": sample.rubric.id},
        )
        assert captured["prompt_text"] == sample.prompt.content
        assert captured["response_text"] == sample.response.content
        assert {c.id for c in captured["criteria"]} == {
            sample.accuracy.id,
            sample.concision.id,
        }
