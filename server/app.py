import os
from pathlib import Path

from dotenv import load_dotenv

# Load env as early as possible, before importing modules that read env at import-time
# Load .env from project root (one level up from server directory)
project_root = os.path.dirname(os.path.dirname(__file__))
env_path = os.path.join(project_root, '.env')

if os.path.exists(env_path):
    load_dotenv(env_path, override=True)
    print(f"Loaded .env from: {env_path}")
else:
    print(f"Warning: .env file not found at {env_path}")

# Also load from server directory (for keys like NVCF_RUN_KEY)
server_env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(server_env_path):
    load_dotenv(server_env_path, override=True)
    print(f"Also loaded .env from: {server_env_path}")


# LangSmith tracing (must run after env load, before agent imports)
try:
    from .infrastructure.langsmith_config import setup_langsmith
    setup_langsmith()
except ImportError:
    try:
        from infrastructure.langsmith_config import setup_langsmith
        setup_langsmith()
    except Exception:
        pass
except Exception:
    pass


from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse, Response

try:
    from .agents.registry import agents
    from .agents.router import init_router
    from .api.limiter import limiter
    from .api.routes import (
        auth, chat_sessions, chat_messages, pipelines, credits,
        reports, admin, three_d_canvases, attachments,
        agents as agents_routes, alphafold, rfdiffusion, proteinmpnn,
        openfold2, diffdock, files, misc,
    )
except ImportError:
    import sys
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    from agents.registry import agents
    from agents.router import init_router
    from api.limiter import limiter
    from api.routes import (
        auth, chat_sessions, chat_messages, pipelines, credits,
        reports, admin, three_d_canvases, attachments,
        agents as agents_routes, alphafold, rfdiffusion, proteinmpnn,
        openfold2, diffdock, files, misc,
    )


app = FastAPI()
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

allowed_origins = os.getenv("APP_ORIGIN", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    # Initialize database (create tables + run pending migrations)
    try:
        from database.db import init_db
    except ImportError:
        from .database.db import init_db
    try:
        init_db()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Warning: Database initialization error: {e}")

    await init_router(list(agents.values()))

    # Suppress harmless Windows asyncio connection reset errors
    import asyncio
    import logging
    import sys

    class ConnectionResetFilter(logging.Filter):
        """Filter out harmless Windows connection reset errors."""
        def filter(self, record):
            if sys.platform == 'win32':
                msg = record.getMessage()
                if 'ConnectionResetError' in msg or 'WinError 10054' in msg:
                    if '_call_connection_lost' in msg or '_ProactorBasePipeTransport' in msg:
                        return False
            return True

    asyncio_logger = logging.getLogger('asyncio')
    asyncio_logger.addFilter(ConnectionResetFilter())

    def handle_exception(loop, context):
        exception = context.get('exception')
        if isinstance(exception, ConnectionResetError):
            if hasattr(exception, 'winerror') and exception.winerror == 10054:
                return
            if sys.platform == 'win32':
                return
        if loop.default_exception_handler:
            loop.default_exception_handler(context)
        else:
            logging.error(f"Unhandled exception in event loop: {context}")

    try:
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(handle_exception)
    except RuntimeError:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.set_exception_handler(handle_exception)
        except Exception:
            pass


# Register API routers — existing
app.include_router(auth.router)
app.include_router(chat_sessions.router)
app.include_router(chat_messages.router)
app.include_router(pipelines.router)
app.include_router(credits.router)
app.include_router(reports.router)
app.include_router(admin.router)
app.include_router(three_d_canvases.router)
app.include_router(three_d_canvases.user_router)
app.include_router(attachments.router)

# Register API routers — new
app.include_router(agents_routes.router)
app.include_router(alphafold.router)
app.include_router(rfdiffusion.router)
app.include_router(proteinmpnn.router)
app.include_router(openfold2.router)
app.include_router(diffdock.router)
app.include_router(files.router)
app.include_router(misc.router)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.exception_handler(RateLimitExceeded)
def _rate_limit_handler(request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"error": "rate_limited", "detail": str(exc)})


# ─── Static File Serving (Production) ────────────────────────────────────────
# In production (Docker), serve the built frontend from the dist/ directory.
# In development, Vite handles this via its dev server + proxy.
_dist_dir = Path(__file__).parent.parent / "dist"
if _dist_dir.exists() and (_dist_dir / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(_dist_dir), html=True), name="frontend")
