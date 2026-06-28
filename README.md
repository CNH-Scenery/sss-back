# CoinTwin MVP

CoinTwin is an MVP for turning a user's market-scenario judgments into a structured decision twin. Session 0 only creates the runnable project skeleton.

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

```powershell
docker compose config
docker compose up --build
```

## Session 0 Scope

Implemented:

- FastAPI `/health`
- backend health test
- backend-worker process entrypoint
- Next.js first screen with backend health display
- PostgreSQL, backend, backend-worker, frontend compose services
- environment example

Not implemented in Session 0:

- database schema
- LLM calls
- Upbit calls
- backtesting logic
- survey flow
