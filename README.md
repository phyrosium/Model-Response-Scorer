# Model Response Scorer

Generate LLM responses to a prompt, score them against a custom rubric by hand,
then have an LLM judge score the same response independently and compare the two
side by side.

**Live demo: <!-- TODO: paste the Railway frontend URL here -->**

## Why

Using a model to grade model output is now a normal way to evaluate at a scale
humans cannot match. It is only worth doing if the judge broadly agrees with a
careful human on cases where you already know the answer. This tool makes that
agreement, or the lack of it, visible on your own prompts and your own rubric
rather than on a benchmark.

So the judge is never shown the manual scores. Anchoring it to a number it was
just handed would turn the comparison into a test of whether the model can copy.

## A real result

Prompt: *"What is the capital of France? Answer in one short sentence."*
Response: *"The capital of France is Paris."* Scored against the **Answer
quality** rubric:

| Criterion | Max | Weight | Manual | Auto | Delta |
| --- | --- | --- | --- | --- | --- |
| Accuracy | 5 | 2 | 5 | 5 | 0 |
| Concision | 3 | 1 | 3 | 3 | 0 |
| Tone | 5 | 1 | 4 | **5** | **+1** |

Weighted total: manual 95%, auto 100%. The disagreement runs both ways. On a
verbose markdown answer to an arithmetic question the judge went the other
direction, scoring Tone 4 against a human 5 and citing "slightly heavy bold and
header formatting for such a short problem".

**The judge is not deterministic.** Rerunning it on an unchanged response with
an unchanged rubric does not reproduce its own answer: one response scored Tone
4 on the first run and 5 on the second, with every rationale rewritten. A single
automated score is a sample, not a measurement, and a one point gap may be judge
variance rather than real disagreement. For anything load bearing, several runs
and the spread between them would be more honest than one number.

## Running locally

```bash
cp .env.example .env    # then add your ANTHROPIC_API_KEY
docker compose up --build
```

Then open http://localhost:5173. The `/about` and `/how-to` pages in the app
explain the workflow.

The stack still starts without an API key. Only `/generate` and `/auto-score`
fail, with a 503 naming what is missing.

On first boot the backend applies migrations and seeds three starter rubrics
(**Answer quality**, **Reasoning quality**, **Instruction following**), so a
fresh clone comes up ready to use. Those are ordinary rows: edit, score against
or delete them like any rubric you build yourself. Both steps are safe to
repeat.

Tests:

```bash
docker compose exec backend pytest
```

Unit tests stub the Anthropic client to cover branches that are awkward to
trigger live, such as a refusal or a reply with no text block. Endpoint tests run
against the real Postgres inside a transaction that is rolled back afterwards, so
the actual constraints and enum type are exercised without leaving rows behind.
Running the suite twice in a row is a good check that the rollback works.

The frontend has no automated tests. It was verified by hand in a browser
against real data, which was judged an acceptable trade for this project.

## Stack

React and TypeScript (Vite), FastAPI, Postgres, orchestrated with Docker
Compose. Three containers on one network: `db`, `backend`, `frontend`.

## Screens

| Route | Purpose |
| --- | --- |
| `/prompts` | Write prompts, generate responses against a chosen model |
| `/rubrics` | Build a rubric with any number of weighted criteria |
| `/scoring` | Pick a prompt, response and rubric, then score each criterion |
| `/comparison` | Run the judge and compare its scores against the manual ones |
| `/how-to` | The workflow in order |
| `/about` | What the tool is for, including the nondeterminism finding |

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness plus a Postgres round trip |
| `POST` | `/prompts` | Create a prompt |
| `GET` | `/prompts` | List prompts, newest first |
| `GET` | `/prompts/{id}/responses` | Responses generated for a prompt |
| `POST` | `/generate` | Send a stored prompt to Claude and persist the reply |
| `POST` | `/rubrics` | Create a rubric together with its criteria |
| `GET` | `/rubrics` | List rubrics with their criteria |
| `GET` | `/rubrics/{id}` | Fetch one rubric |
| `POST` | `/scores` | Upsert the manual score for one criterion |
| `GET` | `/responses/{id}/scores` | Every score on a response, manual and auto |
| `POST` | `/auto-score` | Have the judge score a response against a rubric |

Interactive docs at http://localhost:8000/docs.

## Design decisions worth knowing

**Generation is synchronous.** `/generate` blocks until the model replies, which
suits a small batch scored by hand. Real volume would want a task queue and a job
id instead.

**Only text blocks are stored.** Adaptive thinking is on by default, so a reply
carries thinking blocks alongside text. This is load bearing rather than
cosmetic: `ThinkingBlock` has no `.text` attribute, so iterating `.text` across
every block raises `AttributeError` on any reply that includes reasoning.

**Refusals return 422 and store nothing.** A refusal arrives as HTTP 200 with
`stop_reason == "refusal"`, so that is checked before the content is read. Server
side fallbacks are deliberately not enabled, since they would answer with a
different model while the row still claimed `claude-opus-5`.

**A judge verdict is accepted whole or not at all.** A skipped criterion, an
invented id, a double score or an out of range value rejects the entire batch
with a 502. A half stored verdict would leave the comparison quietly wrong, which
is worse than a visible failure.

**Score writes are upserts.** Resubmitting a cell replaces the previous score
rather than erroring, because a scoring panel is used by changing your mind. A
single `ON CONFLICT DO UPDATE` keeps it atomic, and the row keeps its original
`id` and `created_at`.

**Validation happens at the edge.** Duplicate criterion names, a nonpositive
`max_score`, a negative `weight` and empty criteria lists all return 422 rather
than surfacing as a 500 from a database constraint.

## Database schema

```
prompts ──> responses ──> scores ──> rubric_criteria ──> rubrics
```

Each criterion carries its own `max_score`, so one rubric can mix a 0 to 5 and a
0 to 3 scale, plus a `weight` for aggregates and a `position` for display order.
A weight of 0 means the criterion is scored but excluded from the total.

The `source` enum on `scores` is what makes the comparison work.
`UNIQUE (response_id, criterion_id, source)` lets a human score and a judge score
coexist for the same cell while stopping either side from recording it twice.
Deleting a prompt cascades to its responses and their scores; rubrics are
unaffected.

## Deploying

Both images build and run unmodified on a platform that injects `PORT`. The
backend binds `0.0.0.0:$PORT`, the frontend Dockerfile's default stage is a
production build served by a static server, and all configuration comes from the
environment.

On Railway: add a Postgres plugin, then two services from this repo with root
directories `backend` and `frontend`. Generate both domains first, since each
service needs the other's.

| Service | Variable | Value |
| --- | --- | --- |
| backend | `ANTHROPIC_API_KEY` | your key |
| backend | `FRONTEND_URL` | the frontend domain, for the CORS allowlist |
| backend | `DATABASE_URL` | reference the Postgres service, do not type it |
| frontend | `VITE_API_URL` | the backend domain |

`VITE_API_URL` is read at **build** time, not run time. Vite substitutes it into
the bundle, so changing it needs a redeploy rather than a restart. A deployed app
still calling `localhost:8000` means the bundle was built before the variable was
set. Neither URL should have a trailing slash.

## Notable issues encountered

- Nothing ran `alembic upgrade head`, so a fresh clone came up with no tables at
  all. Migrations and seeding now run from the container entrypoint.
- Alembic's autogenerate omitted the `score_source` enum teardown, so downgrade
  followed by upgrade failed with `DuplicateObject`. The drop was added by hand.
- A UTF-8 BOM on `.env` made Compose read the variable name as
  `﻿ANTHROPIC_API_KEY`, so the key silently never reached the container.
- A CRLF `entrypoint.sh` dies in the Linux container with `set: Illegal option
  -`. `.gitattributes` pins shell scripts to LF so a Windows clone still works.
- `vite preview` answers 403 to any host it does not recognise, which would have
  meant a 403 on every request to a deployed domain. The production stage serves
  the built output with a static server instead.
- `scores.value` has no upper bound in the database, because the maximum lives on
  `rubric_criteria.max_score` in another table and a Postgres check constraint
  cannot reference another row. The ceiling is enforced in the endpoint, so
  writes made straight to Postgres can still violate it.

## Roadmap

- [x] Docker skeleton, schema and migrations
- [x] Prompt create/list and synchronous generation
- [x] Rubric builder (create and read)
- [x] Manual scoring endpoints
- [x] React UI: prompts, rubrics, scoring, comparison
- [x] Auto scoring via LLM judge and the comparison view
- [ ] Remaining prompt CRUD (fetch by id, update, delete)
- [ ] Rubric edit/delete, score delete
- [ ] Frontend tests (deliberate gap, hand verified in a browser instead)
