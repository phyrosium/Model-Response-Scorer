# AI Eval Tool

A tool for generating LLM responses to a set of prompts, scoring them against custom rubrics, and comparing manual vs. automated scoring.

## Status
🚧 Step 1: Docker skeleton — Postgres, FastAPI backend, and React/TypeScript frontend are wired together and can talk to each other. No real features yet.

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

## Architecture
Three containers, one network:
- `db` — Postgres 16
- `backend` — FastAPI, connects to `db`, exposes REST endpoints
- `frontend` — Vite dev server, calls `backend` over HTTP

## Roadmap
- [x] Docker skeleton with health check across all three services
- [ ] Database schema (prompts, responses, rubrics, criteria, scores)
- [ ] Prompt CRUD + LLM generation endpoint
- [ ] Rubric builder
- [ ] Manual scoring UI
- [ ] Auto-scoring via LLM + manual-vs-auto comparison view
