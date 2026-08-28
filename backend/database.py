import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

def normalise_database_url(url: str) -> str:
    """Accept the legacy postgres:// scheme some providers still hand out.

    SQLAlchemy 2 only registers the postgresql:// dialect and rejects the older
    spelling outright with NoSuchModuleError.
    """
    prefix = "postgres://"
    if url.startswith(prefix):
        return "postgresql://" + url[len(prefix) :]
    return url


DATABASE_URL = normalise_database_url(
    os.getenv("DATABASE_URL", "postgresql://eval_user:eval_pass@db:5432/eval_db")
)

# pool_pre_ping avoids handing out connections Postgres has already dropped,
# which happens whenever the db container restarts underneath us
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base shared by every model and by Alembic's autogenerate."""


def get_db():
    """FastAPI dependency: yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
