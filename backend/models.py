"""SQLAlchemy models for the eval pipeline.

The shape follows the flow of the tool: a Prompt is sent to a model to produce
Responses; a Rubric is a named set of RubricCriteria; a Score is one criterion
applied to one response, recorded either by a human or by an LLM judge.
"""

import enum
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class ScoreSource(str, enum.Enum):
    """Which side of the manual-vs-auto comparison a score came from."""

    manual = "manual"
    auto = "auto"


class Prompt(Base):
    __tablename__ = "prompts"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str | None] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    responses: Mapped[list["Response"]] = relationship(
        back_populates="prompt", cascade="all, delete-orphan"
    )


class Response(Base):
    """One model's answer to one prompt."""

    __tablename__ = "responses"

    id: Mapped[int] = mapped_column(primary_key=True)
    prompt_id: Mapped[int] = mapped_column(
        ForeignKey("prompts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # free-form so it survives new model releases without a migration
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    prompt: Mapped["Prompt"] = relationship(back_populates="responses")
    scores: Mapped[list["Score"]] = relationship(
        back_populates="response", cascade="all, delete-orphan"
    )


class Rubric(Base):
    __tablename__ = "rubrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    criteria: Mapped[list["RubricCriterion"]] = relationship(
        back_populates="rubric",
        cascade="all, delete-orphan",
        order_by="RubricCriterion.position",
    )


class RubricCriterion(Base):
    """A single scored dimension within a rubric, e.g. "Factual accuracy"."""

    __tablename__ = "rubric_criteria"
    __table_args__ = (
        UniqueConstraint("rubric_id", "name", name="uq_criterion_rubric_name"),
        CheckConstraint("max_score > 0", name="ck_criterion_max_score_positive"),
        CheckConstraint("weight >= 0", name="ck_criterion_weight_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    rubric_id: Mapped[int] = mapped_column(
        ForeignKey("rubrics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # each criterion carries its own scale, so a rubric can mix 1-5 and 1-10
    max_score: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    # display order in the rubric builder / scoring UI
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    rubric: Mapped["Rubric"] = relationship(back_populates="criteria")
    scores: Mapped[list["Score"]] = relationship(
        back_populates="criterion", cascade="all, delete-orphan"
    )


class Score(Base):
    """One criterion applied to one response, by a human or an LLM judge.

    The (response, criterion, source) uniqueness is what makes the manual-vs-auto
    comparison work: both rows can exist side by side for the same cell, but
    neither side can record the same cell twice.
    """

    __tablename__ = "scores"
    __table_args__ = (
        UniqueConstraint(
            "response_id",
            "criterion_id",
            "source",
            name="uq_score_response_criterion_source",
        ),
        CheckConstraint("value >= 0", name="ck_score_value_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    response_id: Mapped[int] = mapped_column(
        ForeignKey("responses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    criterion_id: Mapped[int] = mapped_column(
        ForeignKey("rubric_criteria.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[ScoreSource] = mapped_column(
        Enum(ScoreSource, name="score_source"), nullable=False
    )
    # float rather than int so an LLM judge can return a fractional score
    value: Mapped[float] = mapped_column(Float, nullable=False)
    # the judge's justification, or the human's note
    rationale: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    response: Mapped["Response"] = relationship(back_populates="scores")
    criterion: Mapped["RubricCriterion"] = relationship(back_populates="scores")
