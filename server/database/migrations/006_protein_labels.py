#!/usr/bin/env python3
"""Migration script to add protein_labels table for session-scoped protein labelling."""

import sqlite3
from pathlib import Path
import sys
import types

migration_file_dir = Path(__file__).parent
server_dir = migration_file_dir.parent.parent

sys.path.insert(0, str(server_dir))

class MockConfig:
    @staticmethod
    def get_server_dir():
        return server_dir

infra_module = types.ModuleType('infrastructure')
config_module = types.ModuleType('infrastructure.config')
config_module.get_server_dir = MockConfig.get_server_dir
infra_module.config = config_module
sys.modules['infrastructure'] = infra_module
sys.modules['infrastructure.config'] = config_module

try:
    from database.db import DB_PATH
except ImportError:
    try:
        from infrastructure.config import get_server_dir
        DB_PATH = Path(get_server_dir()) / "novoprotein.db"
    except Exception:
        DB_PATH = server_dir / "novoprotein.db"


def run_migration():
    """Add protein_labels table if it doesn't exist."""
    try:
        print("Running migration 006: Adding protein_labels table...")
        print(f"Database path: {DB_PATH}")

        if not DB_PATH.exists():
            print(f"Database not found at {DB_PATH}, creating it...")
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='protein_labels'"
        )
        if cursor.fetchone():
            print("protein_labels table already exists, skipping migration")
            conn.close()
            return

        print("Creating protein_labels table...")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS protein_labels (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                short_label TEXT NOT NULL,
                kind TEXT NOT NULL,
                source_tool TEXT,
                file_id TEXT,
                job_id TEXT,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (file_id) REFERENCES user_files(id) ON DELETE SET NULL,
                UNIQUE (session_id, short_label)
            )
        """)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_protein_labels_user_id ON protein_labels(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_protein_labels_session_id ON protein_labels(session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_protein_labels_short_label ON protein_labels(short_label)")

        conn.commit()
        conn.close()

        print("✓ Migration 006 completed successfully: protein_labels table created")
    except Exception as e:
        print(f"✗ Migration 006 failed: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    run_migration()
