# AI Eval Tool

A tool for generating LLM responses to a set of prompts, scoring them against custom rubrics, and comparing manual vs. automated scoring.

## Status
🚧 Step 2: Database schema — the five core tables exist as SQLAlchemy models with an Alembic migration. No API endpoints over them yet.

## Stack
- Frontend: React + TypeScript (Vite)
- Backend: Python + FastAPI
- Database: Postgres
- Orchestration: Docker Compose

## Running locally

```bash
docker compose up --build
```

Then check:
- Frontend: http://localhost:5173 (should show API status + "database: connected")
- Backend health check: http://localhost:8000/health
- Backend root: http://localhost:8000/

### Migrations

Alembic runs inside the backend container, which already has the deps and can reach `db`:

```bash
docker compose exec backend alembic upgrade head
```

After changing anything in `backend/models.py`:

```bash
docker compose exec backend alembic revision --autogenerate -m "what changed"
```

Always read the generated file before applying it — autogenerate does not
notice everything (it missed the `score_source` enum teardown in the initial
migration, which had to be added by hand).

## Architecture
Three containers, one network:
- `db` — Postgres 16
- `backend` — FastAPI, connects to `db`, exposes REST endpoints
- `frontend` — Vite dev server, calls `backend` over HTTP

## Database schema

```
prompts        ──<  responses  ──<  scores  >──  rubric_criteria  >── rubrics
```

- **prompts** — the input text, optionally titled.
- **responses** — one model's answer to one prompt. `model` is a free-form
  string so new model releases don't need a migration.
- **rubrics** — a named, reusable set of criteria. Independent of any prompt.
- **rubric_criteria** — one scored dimension. Each carries its own `max_score`,
  so a single rubric can mix a 1–5 and a 1–10 scale, plus a `weight` for
  weighted aggregates and a `position` for display order.
- **scores** — one criterion applied to one response, tagged `manual` or `auto`.

The `source` enum on `scores` is what makes the manual-vs-auto comparison work.
`UNIQUE (response_id, criterion_id, source)` lets a human score and a judge
score coexist for the same cell while stopping either side from recording that
cell twice. Deleting a prompt cascades to its responses and their scores;
rubrics are unaffected.

## Roadmap
- [x] Docker skeleton with health check across all three services
- [x] Database schema (prompts, responses, rubrics, criteria, scores)
- [ ] Prompt CRUD + LLM generation endpoint
- [ ] Rubric builder
- [ ] Manual scoring UI
- [ ] Auto-scoring via LLM + manual-vs-auto comparison view
