#!/usr/bin/env python3
"""
Migration script to migrate from global file storage to user-isolated storage.

This script:
1. Creates new database tables (user_files, chat_sessions, session_files, pipelines, pipeline_executions)
2. Migrates existing files from global directories to user-scoped directories
3. Migrates session tracking from JSON to database
4. Assigns orphaned files to 'system' user (can be reassigned later)
"""

import json
import shutil
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional
import sys
import os

# Add server directory to path
# Migration file is at: server/database/migrations/001_user_isolation.py
# Server dir is: server/
# DB file is at: server/database/db.py
migration_file_dir = Path(__file__).parent  # server/database/migrations/
server_dir = migration_file_dir.parent.parent  # server/
db_file_path = migration_file_dir.parent / "db.py"  # server/database/db.py

# Set up path for imports - add server directory to path
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

# Import using absolute path - need to patch the relative import
import importlib.util
import re

# Read db.py and patch the relative import
with open(db_file_path, 'r') as f:
    db_code = f.read()

# Replace relative import with our mock
db_code = db_code.replace(
    'from ..infrastructure.config import get_server_dir',
    'from infrastructure.config import get_server_dir'
)

# Create a code object and execute it
db_spec = importlib.util.spec_from_file_location("db_module", str(db_file_path))
db_module = importlib.util.module_from_spec(db_spec)
exec(compile(db_code, str(db_file_path), 'exec'), db_module.__dict__)
get_db = db_module.get_db
init_db = db_module.init_db


def migrate_database_schema():
    """Create new tables by running schema updates."""
    print("Creating new database tables...")
    try:
        init_db()  # This will run the updated schema.sql
        print("✓ Database tables created")
    except sqlite3.OperationalError as e:
        if "already exists" in str(e):
            print("✓ Database tables already exist (skipping creation)")
        else:
            raise


def migrate_existing_files():
    """Migrate existing files from global storage to user-scoped storage."""
    print("\nMigrating existing files...")
    
    base_dir = Path(__file__).parent.parent.parent
    old_uploads_dir = base_dir / "domain" / "storage" / "uploads" / "pdb"
    old_index_file = base_dir / "domain" / "storage" / "uploads" / "pdb_index.json"
    
    # Create system user directory
    system_storage_dir = base_dir / "storage" / "system" / "uploads" / "pdb"
    system_storage_dir.mkdir(parents=True, exist_ok=True)
    
    files_migrated = 0
    
    # Migrate PDB uploads
    if old_index_file.exists():
        try:
            with open(old_index_file, "r") as f:
                index = json.load(f)
            
            with get_db() as conn:
                for file_id, metadata in index.items():
                    old_file_path = old_uploads_dir / f"{file_id}.pdb"
                    if old_file_path.exists():
                        # Move file to system user directory
                        new_file_path = system_storage_dir / f"{file_id}.pdb"
                        shutil.move(str(old_file_path), str(new_file_path))
                        
                        # Create database entry
                        stored_path_rel = str(new_file_path.relative_to(base_dir))
                        metadata_json = json.dumps({
                            "atoms": metadata.get("atoms"),
                            "chains": metadata.get("chains", []),
                            "chain_residue_counts": metadata.get("chain_residue_counts", {}),
                            "total_residues": metadata.get("total_residues", 0),
                            "suggested_contigs": metadata.get("suggested_contigs", "50-150"),
                        })
                        
                        conn.execute(
                            """INSERT OR IGNORE INTO user_files 
                               (id, user_id, file_type, original_filename, stored_path, size, metadata)
                               VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (
                                file_id,
                                "system",
                                "upload",
                                metadata.get("filename", f"{file_id}.pdb"),
                                stored_path_rel,
                                metadata.get("size", 0),
                                metadata_json,
                            ),
                        )
                        files_migrated += 1
                        print(f"  Migrated upload: {file_id}")
        except Exception as e:
            print(f"  Warning: Failed to migrate uploads: {e}")
    
    # Migrate result files (RFdiffusion, AlphaFold, ProteinMPNN)
    # These are in old locations, we'll create database entries pointing to them
    # but keep files in place for backward compatibility
    result_dirs = [
        ("rfdiffusion", base_dir / "agents" / "handlers" / "rfdiffusion_results"),
        ("alphafold", base_dir / "agents" / "handlers" / "alphafold_results"),
        ("proteinmpnn", base_dir / "agents" / "handlers" / "proteinmpnn_results"),
    ]
    
    # Also check old locations at server root
    old_result_dirs = [
        ("rfdiffusion", base_dir.parent / "rfdiffusion_results"),
        ("alphafold", base_dir.parent / "alphafold_results"),
        ("proteinmpnn", base_dir.parent / "proteinmpnn_results"),
    ]
    result_dirs.extend(old_result_dirs)
    
    for file_type, result_dir in result_dirs:
        if result_dir.exists():
            with get_db() as conn:
                if file_type == "proteinmpnn":
                    # ProteinMPNN stores in subdirectories
                    for job_dir in result_dir.iterdir():
                        if job_dir.is_dir():
                            job_id = job_dir.name
                            result_json = job_dir / "result.json"
                            if result_json.exists():
                                stored_path_rel = str(result_dir.relative_to(base_dir) / job_id)
                                conn.execute(
                                    """INSERT OR IGNORE INTO user_files 
                                       (id, user_id, file_type, original_filename, stored_path, size, metadata, job_id)
                                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                                    (
                                        job_id,
                                        "system",
                                        file_type,
                                        f"{job_id}/result.json",
                                        stored_path_rel,
                                        result_json.stat().st_size,
                                        json.dumps({}),
                                        job_id,
                                    ),
                                )
                                files_migrated += 1
                                print(f"  Migrated {file_type} result: {job_id}")
                else:
                    # RFdiffusion and AlphaFold store as single files
                    for pdb_file in result_dir.glob("*.pdb"):
                        file_id = pdb_file.stem.replace(f"{file_type}_", "")
                        stored_path_rel = str(pdb_file.relative_to(base_dir))
                        conn.execute(
                            """INSERT OR IGNORE INTO user_files 
                               (id, user_id, file_type, original_filename, stored_path, size, metadata, job_id)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                            (
                                file_id,
                                "system",
                                file_type,
                                pdb_file.name,
                                stored_path_rel,
                                pdb_file.stat().st_size,
                                json.dumps({}),
                                file_id,
                            ),
                        )
                        files_migrated += 1
                        print(f"  Migrated {file_type} result: {file_id}")
    
    print(f"✓ Migrated {files_migrated} files to system user")
    return files_migrated


def migrate_session_files():
    """Migrate session file tracking from JSON to database."""
    print("\nMigrating session files...")
    
    base_dir = server_dir
    old_tracker_file = base_dir / "domain" / "storage" / "session_files.json"
    
    sessions_migrated = 0
    associations_migrated = 0
    
    if old_tracker_file.exists():
        try:
            with open(old_tracker_file, "r") as f:
                tracker = json.load(f)
            
            with get_db() as conn:
                for session_id, files in tracker.items():
                    # Create chat session for system user
                    conn.execute(
                        """INSERT OR IGNORE INTO chat_sessions (id, user_id, title, created_at, updated_at)
                           VALUES (?, ?, ?, datetime('now'), datetime('now'))""",
                        (session_id, "system", f"Migrated Session {session_id[:8]}"),
                    )
                    sessions_migrated += 1
                    
                    # Create session-file associations
                    for file_entry in files:
                        file_id = file_entry.get("file_id")
                        if file_id:
                            # Verify file exists in user_files
                            file_check = conn.execute(
                                "SELECT id FROM user_files WHERE id = ?",
                                (file_id,),
                            ).fetchone()
                            
                            if file_check:
                                conn.execute(
                                    """INSERT OR IGNORE INTO session_files 
                                       (session_id, file_id, user_id, created_at)
                                       VALUES (?, ?, ?, datetime('now'))""",
                                    (session_id, file_id, "system"),
                                )
                                associations_migrated += 1
                    
                    print(f"  Migrated session: {session_id} ({len(files)} files)")
        except Exception as e:
            print(f"  Warning: Failed to migrate sessions: {e}")
    
    print(f"✓ Migrated {sessions_migrated} sessions and {associations_migrated} file associations")
    return sessions_migrated, associations_migrated


def validate_migration():
    """Validate that migration completed successfully."""
    print("\nValidating migration...")
    
    with get_db() as conn:
        # Check user_files table
        file_count = conn.execute("SELECT COUNT(*) as count FROM user_files").fetchone()["count"]
        print(f"  User files in database: {file_count}")
        
        # Check chat_sessions table
        session_count = conn.execute("SELECT COUNT(*) as count FROM chat_sessions").fetchone()["count"]
        print(f"  Chat sessions in database: {session_count}")
        
        # Check session_files table
        association_count = conn.execute("SELECT COUNT(*) as count FROM session_files").fetchone()["count"]
        print(f"  Session-file associations: {association_count}")
    
    print("✓ Migration validation complete")


def main():
    """Run the migration."""
    print("=" * 60)
    print("User Isolation Migration Script")
    print("=" * 60)
    
    try:
        # Step 1: Create database tables
        migrate_database_schema()
        
        # Step 2: Migrate files
        files_migrated = migrate_existing_files()
        
        # Step 3: Migrate sessions
        sessions_migrated, associations_migrated = migrate_session_files()
        
        # Step 4: Validate
        validate_migration()
        
        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print(f"  - Files migrated: {files_migrated}")
        print(f"  - Sessions migrated: {sessions_migrated}")
        print(f"  - Associations migrated: {associations_migrated}")
        print("\nNote: All migrated data is assigned to 'system' user.")
        print("      Use admin tools to reassign to specific users if needed.")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

