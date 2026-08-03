.PHONY: run dev api web worker artifact-worker install test lint build migrate up down

.DEFAULT_GOAL := run

# Run the API (:8000), ingestion worker, artifact worker, and web app (:3000) together.
# Ctrl-C stops every process started by this target.
run:
	@cd services/api && uv run alembic upgrade head
	@api_pid=""; worker_pid=""; artifact_pid=""; \
	cleanup() { \
		trap - INT TERM EXIT; \
		for pid in "$$api_pid" "$$worker_pid" "$$artifact_pid"; do \
			if [ -n "$$pid" ]; then kill "$$pid" 2>/dev/null || true; fi; \
		done; \
		wait 2>/dev/null || true; \
	}; \
	trap cleanup INT TERM EXIT; \
	( cd services/api && uv run uvicorn app.main:app --reload --port 8000 --no-access-log ) & api_pid=$$!; \
	( cd services/api && uv run python -m app.knowledge_worker ) & worker_pid=$$!; \
	( cd services/api && uv run python -m app.artifact_worker ) & artifact_pid=$$!; \
	npm --workspace apps/web run dev
dev: run

api:
	cd services/api && uv run alembic upgrade head && uv run uvicorn app.main:app --reload --port 8000 --no-access-log

web:
	npm --workspace apps/web run dev

worker:
	cd services/api && uv run python -m app.knowledge_worker

artifact-worker:
	cd services/api && uv run python -m app.artifact_worker

install:
	npm install
	cd services/api && uv sync --extra dev

test:
	npm test

lint:
	npm run lint:web

build:
	npm run build:web

migrate:
	cd services/api && uv run alembic upgrade head

up:
	docker compose up --build

down:
	docker compose down
