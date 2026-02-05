#!/usr/bin/env python3
"""
Migration script to add alphafold_jobs table for long-running job persistence.
"""

import sqlite3
from pathlib import Path
import sys
import os

# Add server directory to path
migration_file_dir = Path(__file__).parent  # server/database/migrations/
server_dir = migration_file_dir.parent.parent  # server/

# Set up path for imports
sys.path.insert(0, str(server_dir))

# Mock infrastructure.config before importing db
class MockConfig:
    @staticmethod
    def get_server_dir():
        return server_dir

# Create mock modules
import types
infra_module = types.ModuleType('infrastructure')
config_module = types.ModuleType('infrastructure.config')
config_module.get_server_dir = MockConfig.get_server_dir
infra_module.config = config_module
sys.modules['infrastructure'] = infra_module
sys.modules['infrastructure.config'] = config_module

# Import db module
try:
    from database.db import DB_PATH
except ImportError:
    # Fallback - determine DB path manually
    try:
        from infrastructure.config import get_server_dir
        DB_PATH = Path(get_server_dir()) / "novoprotein.db"
    except:
        DB_PATH = server_dir / "novoprotein.db"


def run_migration():
    """Add alphafold_jobs table if it doesn't exist"""
    try:
        print(f"Running migration 004: Adding alphafold_jobs table...")
        print(f"Database path: {DB_PATH}")
        
        if not DB_PATH.exists():
            print(f"Database not found at {DB_PATH}, creating it...")
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        # Use direct connection for migration
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        # Check if table already exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='alphafold_jobs'"
        )
        if cursor.fetchone():
            print("alphafold_jobs table already exists, skipping migration")
            return
        
        print("Creating alphafold_jobs table...")
        
        # Create table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alphafold_jobs (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                session_id TEXT,
                sequence TEXT NOT NULL,
                sequence_length INTEGER NOT NULL,
                parameters TEXT, -- JSON parameters
                status TEXT NOT NULL DEFAULT 'queued', -- 'queued'|'running'|'completed'|'error'|'cancelled'
                nvidia_req_id TEXT, -- NVIDIA API request ID for recovery
                result_filepath TEXT, -- Path to result PDB file
                error_message TEXT, -- Error details if failed
                progress REAL DEFAULT 0.0, -- Progress percentage (0-100)
                progress_message TEXT, -- Current status message
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE SET NULL
            )
        """)
        
        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alphafold_jobs_user_id ON alphafold_jobs(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alphafold_jobs_status ON alphafold_jobs(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alphafold_jobs_created_at ON alphafold_jobs(created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alphafold_jobs_nvidia_req_id ON alphafold_jobs(nvidia_req_id)")
        
        conn.commit()
        conn.close()
        
        print("✓ Migration 004 completed successfully: alphafold_jobs table created")
    except Exception as e:
        print(f"✗ Migration 004 failed: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    run_migration()
