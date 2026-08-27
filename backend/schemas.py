"""Pydantic request/response models for the API layer.

Kept separate from the SQLAlchemy models so the wire format can change
independently of the database schema.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# what we send when the caller doesn't name a model
DEFAULT_MODEL = "claude-opus-5"


class PromptCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    content: str = Field(min_length=1)


class PromptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    content: str
    created_at: datetime


class GenerateRequest(BaseModel):
    prompt_id: int
    model: str = DEFAULT_MODEL


class ResponseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    prompt_id: int
    model: str
    content: str
    created_at: datetime
