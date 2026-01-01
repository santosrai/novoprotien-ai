"""Database module for user authentication and management."""

from .db import get_db, init_db, DB_PATH

__all__ = ["get_db", "init_db", "DB_PATH"]

