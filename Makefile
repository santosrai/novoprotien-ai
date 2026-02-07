.PHONY: help setup client server dev lint test

help:
	@echo "Targets: setup, client, server, dev, lint, test"

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

# Run all tests (frontend + backend)
test: test-frontend test-backend

# Run frontend unit tests (Vitest)
test-frontend:
	npx vitest run

# Run backend unit tests (pytest)
test-backend:
	cd server && python3 -m pytest tests/ -v

# Run all tests with coverage
test-coverage:
	npx vitest run --coverage
	cd server && python3 -m pytest tests/ -v --cov=server --cov-report=term-missing

