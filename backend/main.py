import logging

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.orm import Session

import llm
from database import engine, get_db
from models import Prompt, Response
from schemas import GenerateRequest, PromptCreate, PromptOut, ResponseOut

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
