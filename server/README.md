# Server (FastAPI)

This folder contains the Python API server used by the app. It exposes `/api/*` endpoints consumed by the frontend.

## Requirements
- Python 3.10+ and pip
- Optional: OpenAI API key (for semantic router embeddings)
- Required to call LLMs: `ANTHROPIC_API_KEY`

## Quick start (Windows PowerShell)
```powershell
# From project root
# 1) Create venv
if (Get-Command python -ErrorAction SilentlyContinue) { python -m venv .venv } else { py -3 -m venv .venv }

# 2) Install deps
.\.venv\Scripts\python.exe -m pip install -r server\requirements.txt

# 3) Configure env (create server/.env)
@"
APP_ORIGIN=http://localhost:5173
DEBUG_API=1
# Required when invoking agents:
# ANTHROPIC_API_KEY=sk-ant-...
# Optional for semantic routing (embeddings):
# OPENAI_API_KEY=sk-openai-...
# Optional model overrides:
# CLAUDE_CODE_MODEL=claude-3-5-sonnet-20241022
# CLAUDE_CHAT_MODEL=claude-3-5-sonnet-20241022
"@ | Out-File -FilePath server\.env -Encoding ASCII -NoNewline

# 4) Run server
.\.venv\Scripts\python.exe -m uvicorn server.app:app --host 0.0.0.0 --port 8787
```

## Quick start (macOS/Linux)
```bash
# From project root
python3 -m venv .venv
./.venv/bin/python -m pip install -r server/requirements.txt
cat > server/.env << 'EOF'
APP_ORIGIN=http://localhost:5173
DEBUG_API=1
# ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-openai-...
# CLAUDE_CODE_MODEL=claude-3-5-sonnet-20241022
# CLAUDE_CHAT_MODEL=claude-3-5-sonnet-20241022
EOF
./.venv/bin/uvicorn server.app:app --host 0.0.0.0 --port 8787
```

## Endpoints
- GET `/api/health` – health check
- GET `/api/agents` – list agents
- POST `/api/agents/route` – auto-route request to an agent
- POST `/api/agents/invoke` – call a specific agent
- Back-compat: POST `/api/generate`, POST `/api/chat`

Note: LLM-backed endpoints require `ANTHROPIC_API_KEY`. Health and listing agents work without it.

## Frontend integration
The frontend reads `VITE_API_BASE`. For local dev, add this to a `.env` at the project root:
```env
VITE_API_BASE="http://localhost:8787/api"
```
Then run the UI separately with `npm run dev`.

## Alternative Node server (optional)
If you prefer the Node/Express version, use:
```bash
npm run start:server
```
It listens on port 8787 and loads env from the project root `.env`.





