"""Test fixtures backed by the real Postgres.

Each test runs inside a transaction that is rolled back afterwards, so tests
exercise the actual schema -- check constraints, the enum type, cascades, the
unique index the upsert depends on -- without leaving rows behind. That matters
here because the interesting bugs in this API live in the gap between what
Pydantic validates and what the database enforces.
"""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from database import engine, get_db
from main import app
from models import Prompt, Response, Rubric, RubricCriterion


@pytest.fixture
def db():
    connection = engine.connect()
    transaction = connection.begin()
    # create_savepoint turns the endpoint's own db.commit() into a savepoint
    # release inside our outer transaction, so committed work stays visible to
    # the test but is undone by the rollback below
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def sample(db):
    """A response to score, and a rubric whose criteria use different scales.

    The differing max_scores are the point: they're what makes the per-criterion
    ceiling check meaningful rather than a single global bound.
    """
    prompt = Prompt(title="Test prompt", content="What is 2 + 2?")
    response = Response(prompt=prompt, model="claude-opus-5", content="4.")
    unscored = Response(prompt=prompt, model="claude-opus-5", content="Four.")
    rubric = Rubric(name="Fixture rubric")
    accuracy = RubricCriterion(
        rubric=rubric, name="Accuracy", max_score=5, weight=2.0, position=0
    )
    concision = RubricCriterion(
        rubric=rubric, name="Concision", max_score=3, weight=1.0, position=1
    )
    db.add_all([prompt, response, unscored, rubric, accuracy, concision])
    db.flush()
    return SimpleNamespace(
        prompt=prompt,
        response=response,
        unscored=unscored,
        rubric=rubric,
        accuracy=accuracy,
        concision=concision,
    )
