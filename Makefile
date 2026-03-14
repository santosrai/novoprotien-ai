.PHONY: help setup client server dev lint test docker-build docker-up docker-down db-migrate

help:
	@echo "Targets: setup, client, server, dev, lint, test, docker-build, docker-up, docker-down, db-migrate"

# One-shot setup for frontend and backend
setup:
	npm install
	python -m venv .venv && . .venv/bin/activate && pip install -r server/requirements.txt

# Run frontend (Vite dev server)
client:
	npm run dev

# Run backend (uvicorn via npm script)
server:
	npm run start:server

# Run both frontend and backend
dev:
	npm run dev:all

# Lint TypeScript
lint:
	npm run lint

# Run fast tests (frontend + backend unit)
test: test-frontend test-backend-unit

# Run frontend unit tests (Vitest)
test-frontend:
	npx vitest run

# Run all backend tests (unit + integration)
test-backend:
	cd server && python3 -m pytest __tests__/ -v

# Run backend unit tests only (fast, no external deps)
test-backend-unit:
	cd server && python3 -m pytest __tests__/unit/ -v

# Run backend integration tests (need running server/APIs)
test-backend-integration:
	cd server && python3 -m pytest __tests__/integration/ -v

# Run E2E browser tests
test-e2e:
	cd __tests__/e2e && python3 utils/test_runner.py

# Run everything
test-all: test-frontend test-backend test-e2e

# Run all tests with coverage
test-coverage:
	npx vitest run --coverage
	cd server && python3 -m pytest __tests__/unit/ -v --cov=server --cov-report=term-missing

# ---------- Docker ----------

# Build Docker image
docker-build:
	docker build -t novoprotein-ai .

# Start containers (build + detach)
docker-up:
	docker compose up -d --build

# Stop containers
docker-down:
	docker compose down

# Follow container logs
docker-logs:
	docker compose logs -f app

# ---------- Database ----------

# Run pending database migrations
db-migrate:
	cd server && python3 -m database.migrate

# Show migration status
db-migrate-status:
	cd server && python3 -m database.migrate --status

