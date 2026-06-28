# CoinTwin Makefile
# Usage: make <target>

# --- Config ---
VENV        := backend/.venv
PY          := $(VENV)/bin/python
PIP         := $(VENV)/bin/pip
HOST        ?= 0.0.0.0
PORT        ?= 8000

.DEFAULT_GOAL := help

# --- Help ---
.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# --- Setup ---
.PHONY: env
env: ## Create .env from .env.example (won't overwrite)
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")
	@test -f .env && echo ".env ready"

.PHONY: venv
venv: ## Create the backend virtualenv if missing
	@test -d $(VENV) || python3 -m venv $(VENV)

.PHONY: install
install: venv ## Install backend dependencies into the venv
	$(PIP) install --upgrade pip
	$(PIP) install -r backend/requirements.txt

# --- Run ---
.PHONY: run
run: env ## Run the FastAPI backend with auto-reload (loads ../.env)
	cd backend && ./.venv/bin/python -m uvicorn app.main:app --host $(HOST) --port $(PORT) --reload --env-file ../.env

.PHONY: serve
serve: env ## Run the FastAPI backend (no reload, loads ../.env)
	cd backend && ./.venv/bin/python -m uvicorn app.main:app --host $(HOST) --port $(PORT) --env-file ../.env

.PHONY: worker
worker: ## Run the backend worker once
	$(PY) backend-worker/worker.py --once

# --- Test ---
.PHONY: test
test: test-backend test-worker ## Run all tests

.PHONY: test-backend
test-backend: ## Run backend tests
	cd backend && ./.venv/bin/python -m pytest app/tests -q

.PHONY: test-worker
test-worker: ## Run worker tests
	$(PY) -m pytest backend-worker/tests -q

# --- Docker Compose ---
.PHONY: up
up: ## Start all services via docker compose (build + detached)
	docker compose up --build -d

.PHONY: down
down: ## Stop all docker compose services
	docker compose down

.PHONY: build
build: ## Build docker compose images
	docker compose build

.PHONY: logs
logs: ## Tail docker compose logs
	docker compose logs -f

# --- Cleanup ---
.PHONY: clean
clean: ## Remove caches and build artifacts
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -prune -exec rm -rf {} +
	rm -f backend/cointwin.db
