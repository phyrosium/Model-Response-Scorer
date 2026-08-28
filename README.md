# Model Response Scorer

A tool for generating LLM responses to a set of prompts, scoring them against custom rubrics, and comparing manual vs. automated scoring.

## Status
Feature-complete for the original roadmap. Write a prompt, generate a response
from Claude, build a rubric, score the response by hand, have an LLM judge score
it independently, and compare the two side by side.

## Stack
- Frontend: React + TypeScript (Vite)
- Backend: Python + FastAPI
- Database: Postgres
- Orchestration: Docker Compose

## Running locally

```bash
docker compose up --build
```

### API key

`/generate` calls the Anthropic API, so it needs a key. Copy `.env.example`
to `.env` and fill it in. `.env` is gitignored:

```bash
cp .env.example .env
```

`docker-compose.yml` reads `ANTHROPIC_API_KEY` from that file and injects it
into the backend container. It defaults to empty, so the stack still starts
without a key. Only `/generate` fails, with a 503 that says what's missing.

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

Always read the generated file before applying it, since autogenerate does not
notice everything (it missed the `score_source` enum teardown in the initial
migration, which had to be added by hand).

### Tests

```bash
docker compose exec backend pytest
```

`backend/tests/` has two kinds of test:

- **Unit**: stubs the Anthropic client to cover branches that are awkward to
  trigger live (a refusal, a reply with no text block, a missing API key), plus
  the Pydantic validation rules.
- **Endpoint**: runs against the real Postgres inside a transaction that is
  rolled back after each test, so the actual constraints, enum type and unique
  index are exercised without leaving rows behind. This is where the paths
  Pydantic can't reach are covered: the per-criterion ceiling, the 404s, the
  duplicate-rubric 409, and the upsert.

The suite needs the `db` service up. It leaves the database exactly as it found
it, so running it twice in a row is a good check that the rollback is working.

## Frontend

Three routes behind `react-router`:

| Route | Screen |
| --- | --- |
| `/prompts` | Write prompts, generate responses against a chosen model, read them back |
| `/rubrics` | Build a rubric with any number of criteria; list existing ones |
| `/scoring` | Pick a prompt → response → rubric, then score each criterion |
| `/comparison` | Run the LLM judge and compare its scores against the manual ones |
| `/how-to` | The workflow in order, from writing a prompt to comparing scores |
| `/about` | What the tool is for, including the judge non-determinism finding |

`src/api/client.ts` is the only place that talks to the backend. It flattens
FastAPI's two error shapes into one string, because `detail` is a plain string for an
`HTTPException` but an array of field objects for a 422, and rendering the
array directly would show `[object Object]` on every validation failure.

The scoring panel prefills from existing manual scores, so re-opening a
response shows what you already gave it and the buttons read *Update* rather
than *Save*. It shows a running weighted total: each criterion contributes
`value / max_score * weight`, divided by the total weight of the criteria that
have been scored so far.

The comparison screen puts both sources in one table with a per-criterion delta,
both rationales, and a summary line: how many criteria the two sides agreed on
exactly, the mean absolute difference, and each side's weighted total.

**Known gap: the frontend has no automated tests.** Everything here was verified
by hand in a browser against real data. Adding coverage would mean Vitest,
Testing Library and a mocked API layer; that was judged not worth the scope for
this project.

## Architecture
Three containers, one network:
- `db`: Postgres 16
- `backend`: FastAPI, connects to `db`, exposes REST endpoints
- `frontend`: Vite dev server, calls `backend` over HTTP

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | API liveness plus a Postgres round-trip |
| `POST` | `/prompts` | Create a prompt (`content` required, `title` optional) |
| `GET` | `/prompts` | List prompts, newest first |
| `POST` | `/generate` | Send a stored prompt to Claude and persist the reply |
| `POST` | `/rubrics` | Create a rubric together with its criteria |
| `GET` | `/rubrics` | List rubrics, each with its criteria |
| `GET` | `/rubrics/{id}` | Fetch one rubric |
| `POST` | `/scores` | Upsert the manual score for one criterion on one response |
| `GET` | `/responses/{id}/scores` | Every score on a response, manual and auto |
| `POST` | `/auto-score` | Have an LLM judge score a response against a whole rubric |

Interactive docs are at http://localhost:8000/docs.

### Generation is synchronous

`POST /generate` takes a `prompt_id` and an optional `model` (defaults to
`claude-opus-5`), calls the Anthropic API, and blocks until the reply comes
back. That is a deliberate choice for this project's workload, which is a small batch
of responses generated by hand. A production version handling real volume
would put generation behind a task queue and return a job id immediately;
that's noted as a future improvement rather than built now.

Two details worth knowing about the call:

- Adaptive thinking is on by default on Opus 5, so the response contains
  thinking blocks alongside text. Only `type == "text"` blocks are stored.
  This is load-bearing rather than cosmetic: `ThinkingBlock` has no `.text`
  attribute at all, so iterating `.text` across every block raises
  `AttributeError` on any reply that includes reasoning.
- A refusal comes back as HTTP 200 with `stop_reason == "refusal"`, so that is
  checked before the content is read. Refusals return 422 and store nothing.
  Server-side fallbacks are deliberately *not* enabled: they would silently
  answer with a different model while the row still said `claude-opus-5`,
  which would corrupt any model comparison.

Nothing is written to `responses` unless generation succeeds.

### Rubrics

A rubric is created in one call along with all of its criteria. There is no
separate add-criterion endpoint, so a rubric must be posted with at least one
criterion or it could never be scored against.

`position` is assigned from the order criteria appear in the request rather
than being accepted from the client, so display order is whatever order you
sent. A `weight` of 0 is legal and means the criterion is scored but excluded
from any weighted aggregate.

Validation happens at the edge rather than falling through to Postgres:
duplicate criterion names, a non-positive `max_score`, a negative `weight`, or
an empty criteria list all return 422. A duplicate rubric name returns 409.
Failed creates roll back cleanly, with no orphaned criteria.

### Scoring

`POST /scores` records manual scores only. `source` is not accepted from the
client, since letting a caller claim `auto` would corrupt the very comparison
this tool exists to make. It is set server-side to `manual`.

The interesting validation is the per-criterion ceiling. `scores.value` has a
`>= 0` check constraint in the database but **no upper bound**, because the
maximum lives on `rubric_criteria.max_score` in a different table, and Postgres
check constraints can't reference another row. Verified directly: a raw
`INSERT` of 99 against a `max_score = 3` criterion is accepted by the database.
So `POST /scores` looks the criterion up and rejects anything above its
`max_score` with a 422. That guard exists only at the API layer; writes made
straight to Postgres can still violate it.

`POST /scores` is an upsert: re-submitting a cell replaces the existing manual
score rather than erroring, because a scoring panel is used by changing your
mind. It's a single `ON CONFLICT DO UPDATE` rather than a read-then-write, so
two concurrent submissions for the same cell can't both insert. The row keeps
its original `id` and `created_at`.

`GET /responses/{id}/scores` returns manual and auto scores together, each
tagged with its `source` and carrying enough of the criterion (name, max_score,
weight) to render without a second request. Results are ordered by criterion
position. Auto scores don't exist yet, but the endpoint was verified against an
injected auto row so the comparison view can read from it unchanged.

### Auto-scoring

`POST /auto-score` takes a response and a rubric, sends both to Claude with the
criteria and their scales, and stores one `auto` score per criterion. It uses
structured outputs (`client.messages.parse`) so the verdict comes back as a
validated object rather than prose to be parsed.

Two decisions matter more than the rest:

**The judge is never shown the manual scores.** Anchoring it to the human's
numbers would make the comparison meaningless, since it would be measuring how well
Claude copies a number it was just handed. There is a test asserting the manual
rationale never appears in anything sent to the judge.

**A verdict is accepted whole or not at all.** If the judge skips a criterion,
invents an id that isn't in the rubric, scores one twice, or returns a value
outside that criterion's range, the entire batch is rejected with a 502 and
nothing is written. A half-stored verdict would leave the comparison view
quietly wrong, which is worse than a visible failure.

Re-running is an upsert, like manual scoring, so a second opinion replaces the
first rather than accumulating.

**On non-determinism:** running the judge twice on the same response with the
same rubric does not reliably give the same answer. Observed during development:
one response scored Tone 4 on the first run and 5 on the second, with different
rationales both times. That is worth knowing before treating a single auto score
as ground truth. For anything load-bearing, several runs would be more honest
than one.

## Database schema

```
prompts        ──<  responses  ──<  scores  >──  rubric_criteria  >── rubrics
```

- **prompts**: the input text, optionally titled.
- **responses**: one model's answer to one prompt. `model` is a free-form
  string so new model releases don't need a migration.
- **rubrics**: a named, reusable set of criteria. Independent of any prompt.
- **rubric_criteria**: one scored dimension. Each carries its own `max_score`,
  so a single rubric can mix a 1–5 and a 1–10 scale, plus a `weight` for
  weighted aggregates and a `position` for display order.
- **scores**: one criterion applied to one response, tagged `manual` or `auto`.

The `source` enum on `scores` is what makes the manual-vs-auto comparison work.
`UNIQUE (response_id, criterion_id, source)` lets a human score and a judge
score coexist for the same cell while stopping either side from recording that
cell twice. Deleting a prompt cascades to its responses and their scores;
rubrics are unaffected.

## Roadmap
- [x] Docker skeleton with health check across all three services
- [x] Database schema (prompts, responses, rubrics, criteria, scores)
- [x] Prompt create/list + synchronous LLM generation endpoint
- [ ] Remaining prompt CRUD (fetch by id, update, delete)
- [x] Rubric builder (create + read)
- [ ] Rubric edit/delete
- [x] Manual scoring endpoints
- [ ] Score delete (update is handled by the upsert)
- [x] React UI: prompt list, rubric builder, scoring panel, comparison view
- [x] Auto-scoring via LLM + manual-vs-auto comparison view
- [ ] Frontend tests (deliberate gap, hand-verified in a browser instead)
