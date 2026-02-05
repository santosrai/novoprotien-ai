"""Database connection and initialization."""

import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Generator
import os

try:
    # Try relative import first (when running as module)
    from ..infrastructure.config import get_server_dir
except ImportError:
    # Fallback to absolute import (when running directly)
    from infrastructure.config import get_server_dir

# Database path - can be overridden by environment variable
DB_PATH = Path(os.getenv("DATABASE_PATH", get_server_dir() / "novoprotein.db"))


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for database connections."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Initialize database with all tables."""
    # Ensure database directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Read schema SQL
    schema_path = Path(__file__).parent / "schema.sql"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    
    # Execute schema
    with get_db() as conn:
        conn.executescript(schema_sql)

