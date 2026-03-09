"""CORS middleware configuration."""

import os
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI


def _parse_origins() -> list[str]:
    configured = os.getenv("APP_ORIGIN", "").strip()
    if not configured:
        return ["http://localhost:5173", "http://127.0.0.1:5173"]
    origins = [origin.strip() for origin in configured.split(",") if origin.strip()]
    filtered = [origin for origin in origins if origin != "*"]
    return filtered or ["http://localhost:5173", "http://127.0.0.1:5173"]


def setup_cors(app: FastAPI) -> None:
    """Set up CORS middleware."""
    allowed_origins = _parse_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

