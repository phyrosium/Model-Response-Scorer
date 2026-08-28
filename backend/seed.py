"""Give a fresh database a few starter rubrics.

These are ordinary rows. Nothing in the application treats them as special, so
they can be edited or deleted exactly like a rubric built through the UI.

The seed is skipped whenever the rubrics table already has anything in it. That
is deliberate: checking per rubric name would resurrect a starter rubric every
time the container restarted, which would make it undeletable in practice.
"""

import logging

from sqlalchemy import func, select

from database import SessionLocal
from models import Rubric, RubricCriterion

logger = logging.getLogger(__name__)

STARTER_RUBRICS = [
    {
        "name": "Answer quality",
        "description": "General purpose rubric for short factual answers.",
        "criteria": [
            {
                "name": "Accuracy",
                "description": "Is the answer factually correct? Weighted double, since a wrong answer is not redeemed by being well written.",
                "max_score": 5,
                "weight": 2.0,
            },
            {
                "name": "Concision",
                "description": "Does it answer without padding, preamble or restating the question? Scored out of 3 because the distinctions here are coarser.",
                "max_score": 3,
                "weight": 1.0,
            },
            {
                "name": "Tone",
                "description": "Neutral and direct, with no sycophancy or hedging.",
                "max_score": 5,
                "weight": 1.0,
            },
        ],
    },
    {
        "name": "Reasoning quality",
        "description": "For prompts where the working matters as much as the answer.",
        "criteria": [
            {
                "name": "Logic",
                "description": "Does each step follow from the last, with no leaps or circular steps?",
                "max_score": 5,
                "weight": 2.0,
            },
            {
                "name": "Clarity",
                "description": "Can the reasoning be followed without rereading it?",
                "max_score": 5,
                "weight": 1.0,
            },
            {
                "name": "Answer stated",
                "description": "Is the final answer given plainly rather than left implicit in the working?",
                "max_score": 3,
                "weight": 1.0,
            },
        ],
    },
    {
        "name": "Instruction following",
        "description": "For prompts that impose explicit constraints, such as a format, a length or a persona.",
        "criteria": [
            {
                "name": "Completeness",
                "description": "Was every part of the request addressed, including any secondary asks?",
                "max_score": 5,
                "weight": 2.0,
            },
            {
                "name": "Constraint adherence",
                "description": "Were stated limits respected, for example word counts, forbidden topics or a required persona?",
                "max_score": 5,
                "weight": 2.0,
            },
            {
                "name": "Format",
                "description": "Does the output match the requested shape, such as JSON, a table or a bulleted list?",
                "max_score": 3,
                "weight": 1.0,
            },
        ],
    },
]


def seed(db=None) -> int:
    """Insert the starter rubrics if there are none. Returns how many were added.

    Takes an optional session so tests can run it inside their own transaction.
    """
    owns_session = db is None
    if owns_session:
        db = SessionLocal()
    try:
        existing = db.scalar(select(func.count()).select_from(Rubric))
        if existing:
            logger.info(
                "seed skipped: %s rubric(s) already present", existing
            )
            return 0

        for spec in STARTER_RUBRICS:
            rubric = Rubric(name=spec["name"], description=spec["description"])
            for position, criterion in enumerate(spec["criteria"]):
                rubric.criteria.append(
                    RubricCriterion(position=position, **criterion)
                )
            db.add(rubric)

        db.commit()
        logger.info("seeded %s starter rubrics", len(STARTER_RUBRICS))
        return len(STARTER_RUBRICS)
    finally:
        if owns_session:
            db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="seed: %(message)s")
    seed()
