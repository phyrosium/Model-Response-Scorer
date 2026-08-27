"""Pydantic request/response models for the API layer.

Kept separate from the SQLAlchemy models so the wire format can change
independently of the database schema.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class RubricCriterionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    # mirrors the DB check constraints, so a bad value is a 422 rather than a 500
    max_score: int = Field(default=5, gt=0)
    weight: float = Field(default=1.0, ge=0)


class RubricCriterionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    max_score: int
    weight: float
    position: int


class RubricCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    # at least one criterion: there is no add-criterion endpoint yet, so an empty
    # rubric could never become useful. `position` is taken from list order
    # rather than being client-supplied.
    criteria: list[RubricCriterionCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def _reject_duplicate_criterion_names(self):
        names = [c.name for c in self.criteria]
        duplicates = sorted({n for n in names if names.count(n) > 1})
        if duplicates:
            raise ValueError(f"duplicate criterion names: {duplicates}")
        return self


class RubricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    created_at: datetime
    criteria: list[RubricCriterionOut]
