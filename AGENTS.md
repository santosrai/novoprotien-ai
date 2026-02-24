# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

NovoProtein AI is a molecular visualization and protein design platform with a React/TypeScript frontend (Vite, port 3000) and a Python FastAPI backend (Uvicorn, port 8787). SQLite is embedded (auto-created at `server/novoprotein.db`). See `Makefile` for the canonical dev commands.

### Running services

- **Both servers**: `npm run dev:all` (uses `npm-run-all --parallel`)
- **Backend only**: `.venv/bin/uvicorn server.app:app --host 0.0.0.0 --port 8787`
- **Frontend only**: `npm run dev`
- The Vite dev server proxies `/api` requests to `localhost:8787`.

### Required secrets

- `OPENROUTER_API_KEY` — required for AI chat and agent features. Without it the app loads but chat returns errors.
- Optional: `NVCF_RUN_KEY`, `OPENAI_API_KEY`, `PINECONE_API_KEY`, `LANGSMITH_API_KEY`.

### Lint / Test / Build

- **Frontend lint**: `npm run lint` — requires `.eslintrc.cjs` (ESLint 8, TypeScript parser). Pre-existing lint errors exist in the codebase (`no-explicit-any`, `no-unused-vars`).
- **Frontend tests**: `npm run test` (Vitest)
- **Backend tests**: `cd server && /workspace/.venv/bin/python3 -m pytest tests/ -v` — 3 pre-existing test failures (stale mocks/assertions).
- **TypeScript check**: `npx tsc --noEmit` — 1 pre-existing error from unbuilt pipeline-canvas library.

### Gotchas

- The `.env` file is loaded from the project root by `python-dotenv` with `override=True`. Do not put API keys in `.env` if they are already set as environment variables, as `.env` values will override them.
- `python3.12-venv` system package must be installed before creating the venv (`sudo apt-get install -y python3.12-venv`).
- `pytest` is not in `server/requirements.txt` — install it separately: `.venv/bin/pip install pytest pytest-cov pytest-asyncio`.
- The 3D Molstar viewer requires WebGL. In headless/remote environments it will show a "WebGL not available" message — this is expected and does not affect chat or API functionality.
