import logging

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

import llm
from database import engine, get_db
from models import Prompt, Response, Rubric, RubricCriterion, Score, ScoreSource
from schemas import (
    GenerateRequest,
    PromptCreate,
    PromptOut,
    ResponseOut,
    RubricCreate,
    RubricOut,
    ScoreCreate,
    ScoreOut,
)

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="AI Eval Tool API")

# Allow the frontend (running on a different port/container) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this before deploying anywhere real
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    """Confirms the API is up and can reach Postgres."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e}"

    return {"status": "ok", "database": db_status}


@app.get("/")
def root():
    return {"message": "AI Eval Tool API is running"}


@app.post("/prompts", response_model=PromptOut, status_code=201)
def create_prompt(payload: PromptCreate, db: Session = Depends(get_db)):
    prompt = Prompt(title=payload.title, content=payload.content)
    db.add(prompt)
    db.commit()
    # created_at is a server default, so it isn't populated until we read it back
    db.refresh(prompt)
    return prompt


@app.get("/prompts", response_model=list[PromptOut])
def list_prompts(db: Session = Depends(get_db)):
    return list(db.scalars(select(Prompt).order_by(Prompt.created_at.desc())).all())


@app.post("/generate", response_model=ResponseOut, status_code=201)
def generate_response(payload: GenerateRequest, db: Session = Depends(get_db)):
    """Send a stored prompt to Claude and persist the reply.

    Synchronous: this blocks for as long as the model takes.
    """
    prompt = db.get(Prompt, payload.prompt_id)
    if prompt is None:
        raise HTTPException(404, f"No prompt with id {payload.prompt_id}")

    try:
        content = llm.generate(prompt.content, payload.model)
    except llm.GenerationError as e:
        # nothing is written if generation failed -- no half-rows in responses
        raise HTTPException(e.status_code, e.message) from e

    response = Response(prompt_id=prompt.id, model=payload.model, content=content)
    db.add(response)
    db.commit()
    db.refresh(response)
    return response


def _load_rubric(db: Session, rubric_id: int) -> Rubric | None:
    """Fetch one rubric with its criteria eagerly loaded.

    The eager load is what keeps the list endpoint off an N+1: measured at 2
    queries with selectinload versus 1+N without, since serializing each rubric
    touches its criteria.
    """
    return db.scalars(
        select(Rubric)
        .where(Rubric.id == rubric_id)
        .options(selectinload(Rubric.criteria))
    ).one_or_none()


@app.post("/rubrics", response_model=RubricOut, status_code=201)
def create_rubric(payload: RubricCreate, db: Session = Depends(get_db)):
    """Create a rubric and its criteria in one call.

    Criteria keep the order they were sent in; `position` is assigned here rather
    than trusted from the client.
    """
    rubric = Rubric(name=payload.name, description=payload.description)
    for position, criterion in enumerate(payload.criteria):
        rubric.criteria.append(
            RubricCriterion(
                name=criterion.name,
                description=criterion.description,
                max_score=criterion.max_score,
                weight=criterion.weight,
                position=position,
            )
        )

    db.add(rubric)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            409, f"A rubric named {payload.name!r} already exists."
        ) from e

    return _load_rubric(db, rubric.id)


@app.get("/rubrics", response_model=list[RubricOut])
def list_rubrics(db: Session = Depends(get_db)):
    return list(
        db.scalars(
            select(Rubric)
            .options(selectinload(Rubric.criteria))
            .order_by(Rubric.created_at.desc())
        ).all()
    )


@app.get("/rubrics/{rubric_id}", response_model=RubricOut)
def get_rubric(rubric_id: int, db: Session = Depends(get_db)):
    rubric = _load_rubric(db, rubric_id)
    if rubric is None:
        raise HTTPException(404, f"No rubric with id {rubric_id}")
    return rubric


@app.post("/scores", response_model=ScoreOut, status_code=201)
def create_score(payload: ScoreCreate, db: Session = Depends(get_db)):
    """Record a manual score for one criterion on one response."""
    if db.get(Response, payload.response_id) is None:
        raise HTTPException(404, f"No response with id {payload.response_id}")

    criterion = db.get(RubricCriterion, payload.criterion_id)
    if criterion is None:
        raise HTTPException(404, f"No criterion with id {payload.criterion_id}")

    # the database only enforces value >= 0; the ceiling is per-criterion, so it
    # has to be checked here or a 5-point criterion would happily accept a 99
    if payload.value > criterion.max_score:
        raise HTTPException(
            422,
            f"value {payload.value} exceeds max_score {criterion.max_score} "
            f"for criterion {criterion.name!r}",
        )

    score = Score(
        response_id=payload.response_id,
        criterion_id=payload.criterion_id,
        source=ScoreSource.manual,
        value=payload.value,
        rationale=payload.rationale,
    )
    db.add(score)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            409,
            f"criterion {criterion.name!r} already has a manual score for "
            f"response {payload.response_id}",
        ) from e

    return _load_score(db, score.id)


def _load_score(db: Session, score_id: int) -> Score | None:
    return db.scalars(
        select(Score).where(Score.id == score_id).options(joinedload(Score.criterion))
    ).one_or_none()


@app.get("/responses/{response_id}/scores", response_model=list[ScoreOut])
def list_scores_for_response(response_id: int, db: Session = Depends(get_db)):
    """Every score on a response, manual and auto alike.

    Auto scores don't exist yet, but the shape is already source-tagged so the
    comparison view can read from this endpoint unchanged.
    """
    if db.get(Response, response_id) is None:
        raise HTTPException(404, f"No response with id {response_id}")

    return list(
        db.scalars(
            select(Score)
            .where(Score.response_id == response_id)
            .options(joinedload(Score.criterion))
            .join(Score.criterion)
            .order_by(RubricCriterion.position, Score.source)
        ).all()
    )
