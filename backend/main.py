import logging
import os

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
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
    AutoScoreRequest,
    RubricCreate,
    RubricOut,
    ScoreCreate,
    ScoreOut,
)

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Model Response Scorer API")

# The local dev server always stays allowed, so a deployment setting
# FRONTEND_URL does not break `docker compose up`.
LOCAL_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def allowed_origins() -> list[str]:
    """Local dev origins, plus whatever FRONTEND_URL names.

    FRONTEND_URL accepts a comma-separated list so a deployment can allow more
    than one domain. Trailing slashes are stripped because a browser never puts
    one on the Origin header, and an origin that does not match exactly is
    silently refused.
    """
    configured = [
        origin.strip().rstrip("/")
        for origin in os.getenv("FRONTEND_URL", "").split(",")
        if origin.strip()
    ]
    return [*LOCAL_ORIGINS, *configured]


app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
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
    return {"message": "Model Response Scorer API is running"}


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


@app.get("/prompts/{prompt_id}/responses", response_model=list[ResponseOut])
def list_responses_for_prompt(prompt_id: int, db: Session = Depends(get_db)):
    """Every generated response for a prompt, newest first.

    This is how the scoring and comparison screens choose what to score.
    """
    if db.get(Prompt, prompt_id) is None:
        raise HTTPException(404, f"No prompt with id {prompt_id}")

    return list(
        db.scalars(
            select(Response)
            .where(Response.prompt_id == prompt_id)
            .order_by(Response.created_at.desc())
        ).all()
    )


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

    Serializing a rubric touches its criteria, so without the eager load the
    list endpoint would issue an extra query per rubric.
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


@app.post("/scores", response_model=ScoreOut)
def upsert_score(payload: ScoreCreate, db: Session = Depends(get_db)):
    """Record or replace the manual score for one criterion on one response.

    Upsert rather than create-only: a scoring panel is used by changing your mind,
    so re-submitting a cell has to overwrite instead of erroring. This is a single
    ON CONFLICT statement rather than a read-then-write, which keeps it atomic --
    two concurrent submissions for the same cell can't both insert.
    """
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

    statement = (
        pg_insert(Score)
        .values(
            response_id=payload.response_id,
            criterion_id=payload.criterion_id,
            source=ScoreSource.manual,
            value=payload.value,
            rationale=payload.rationale,
        )
        .on_conflict_do_update(
            constraint="uq_score_response_criterion_source",
            set_={"value": payload.value, "rationale": payload.rationale},
        )
        .returning(Score.id)
    )
    score_id = db.scalar(statement)
    db.commit()

    return _load_score(db, score_id)


def _load_score(db: Session, score_id: int) -> Score | None:
    return db.scalars(
        select(Score).where(Score.id == score_id).options(joinedload(Score.criterion))
    ).one_or_none()


@app.get("/responses/{response_id}/scores", response_model=list[ScoreOut])
def list_scores_for_response(response_id: int, db: Session = Depends(get_db)):
    """Every score on a response, manual and auto alike.

    Each entry carries its source, so the comparison view reads both sides from
    this one endpoint.
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


@app.post("/auto-score", response_model=list[ScoreOut], status_code=201)
def auto_score(payload: AutoScoreRequest, db: Session = Depends(get_db)):
    """Have an LLM judge score a response against every criterion in a rubric.

    All criteria are written or none are. A judge that misreads the rubric --
    skipping a criterion, inventing one, going out of range -- is rejected whole
    rather than half-stored, which would leave the comparison view quietly wrong.
    """
    response = db.get(Response, payload.response_id)
    if response is None:
        raise HTTPException(404, f"No response with id {payload.response_id}")

    rubric = _load_rubric(db, payload.rubric_id)
    if rubric is None:
        raise HTTPException(404, f"No rubric with id {payload.rubric_id}")

    criteria = [
        llm.JudgeCriterion(
            id=c.id, name=c.name, description=c.description, max_score=c.max_score
        )
        for c in rubric.criteria
    ]

    try:
        verdicts = llm.judge(
            prompt_text=response.prompt.content,
            response_text=response.content,
            criteria=criteria,
            model=payload.model,
        )
    except llm.GenerationError as e:
        raise HTTPException(e.status_code, e.message) from e

    written: list[int] = []
    for verdict in verdicts:
        statement = (
            pg_insert(Score)
            .values(
                response_id=response.id,
                criterion_id=verdict.criterion_id,
                source=ScoreSource.auto,
                value=verdict.value,
                rationale=verdict.rationale,
            )
            .on_conflict_do_update(
                constraint="uq_score_response_criterion_source",
                set_={"value": verdict.value, "rationale": verdict.rationale},
            )
            .returning(Score.id)
        )
        written.append(db.scalar(statement))
    db.commit()

    return [_load_score(db, score_id) for score_id in written]
