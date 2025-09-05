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

# Run Python tests (uses venv if present)
test:
	@if [ -x ./.venv/bin/pytest ]; then ./.venv/bin/pytest -q; else pytest -q; fi

