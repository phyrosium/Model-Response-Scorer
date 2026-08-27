import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text

app = FastAPI(title="AI Eval Tool API")

# Allow the frontend (running on a different port/container) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this before deploying anywhere real
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://eval_user:eval_pass@db:5432/eval_db"
)
engine = create_engine(DATABASE_URL)


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
