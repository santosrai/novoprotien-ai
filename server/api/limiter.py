"""Shared rate-limiter instance for all route files."""

import os

from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request

DEBUG_API = os.getenv("DEBUG_API", "0") == "1"


def _rate_limit_key(request: Request) -> str:
    """In debug mode, use unique key per request to avoid localhost rate limit exhaustion."""
    if DEBUG_API:
        return f"dev-{id(request)}"
    return get_remote_address(request)


limiter = Limiter(key_func=_rate_limit_key)
