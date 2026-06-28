# CoinTwin MVP

CoinTwin is an MVP for turning a user's market-scenario judgments into a structured decision twin.

## Structure

```text
backend/         FastAPI API service
backend-worker/  Separate worker entrypoint
frontend/        Next.js app
docker-compose.yml
```

## Local Backend Test

```powershell
cd backend
python -m pytest app/tests -q
```

The backend currently includes:

- FastAPI `/health`
- SQLModel table models for the MVP domain
- anonymous user seed helper
- OpenAPI-visible API contract stubs
- model metadata and API contract tests

## Worker Startup Check

```powershell
python backend-worker/worker.py --once
```

## Frontend Session 0 Verification

```powershell
cd frontend
node scripts/verify-session0.mjs
```

## Docker Compose

Create a local environment file before running compose:

```powershell
Copy-Item .env.example .env
```

Set `LLM_API_KEY` in `.env`. The real `.env` file is ignored by git and must not be committed.

```powershell
docker compose config
docker compose up --build
```

## Current Scope

Implemented:

- FastAPI `/health`
- backend health test
- backend-worker process entrypoint
- Next.js first screen with backend health display
- PostgreSQL, backend, backend-worker, frontend compose services
- environment example
- SQLModel table metadata
- API contract stubs for scenarios, responses, twin contexts, strategies, backtests, feedbacks, watchlists, and signals

Not implemented yet:

- LLM calls
- Upbit calls
- backtesting logic
- survey flow
- real database CRUD per API
