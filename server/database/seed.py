#!/usr/bin/env python3
"""
Database seed script that:
1. Drops all existing tables
2. Recreates all tables from schema.sql
3. Inserts test user data (user1@gmail.com / test12345)
"""

import sqlite3
import uuid
from pathlib import Path
from datetime import datetime
import sys
import os

# Add server directory to path for imports
seed_file_dir = Path(__file__).parent  # server/database/
server_dir = seed_file_dir.parent  # server/
sys.path.insert(0, str(server_dir))

# Import database utilities
try:
    from database.db import get_db, DB_PATH
except ImportError:
    # Fallback for direct execution
    from db import get_db, DB_PATH

# Import auth utilities - use bcrypt directly to avoid jwt dependency
try:
    import bcrypt
    def hash_password(password: str) -> str:
        """Hash password using bcrypt."""
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
except ImportError:
    # Try importing from infrastructure.auth as fallback
    try:
        from infrastructure.auth import hash_password
    except (ImportError, ModuleNotFoundError):
        print("ERROR: bcrypt module not found. Please install dependencies:")
        print("  pip install bcrypt")
        print("\nOr activate the virtual environment:")
        print("  source server/venv/bin/activate")
        print("  pip install -r server/requirements.txt")
        sys.exit(1)


def get_all_tables(conn: sqlite3.Connection) -> list[str]:
    """Get list of all table names from the database."""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    return [row[0] for row in cursor.fetchall()]


def drop_all_tables(conn: sqlite3.Connection) -> None:
    """Drop all tables in reverse dependency order."""
    print("Dropping all existing tables...")
    
    # Disable foreign key constraints during drops
    conn.execute("PRAGMA foreign_keys=OFF")
    
    # Get all tables
    tables = get_all_tables(conn)
    
    if not tables:
        print("  ✓ No tables to drop")
        return
    
    # Drop all tables (SQLite will handle dependencies if foreign keys are off)
    for table in tables:
        try:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
            print(f"  ✓ Dropped table: {table}")
        except sqlite3.OperationalError as e:
            print(f"  ⚠ Warning: Could not drop {table}: {e}")
    
    # Re-enable foreign key constraints
    conn.execute("PRAGMA foreign_keys=ON")
    print(f"  ✓ Dropped {len(tables)} tables\n")


def recreate_schema(conn: sqlite3.Connection) -> None:
    """Recreate all tables from schema.sql."""
    print("Recreating database schema from schema.sql...")
    
    # Read schema.sql file
    schema_path = Path(__file__).parent / "schema.sql"
    
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    
    # Execute schema
    conn.executescript(schema_sql)
    print("  ✓ Schema executed successfully")
    
    # Verify tables were created (must match schema.sql)
    tables = get_all_tables(conn)
    expected_tables = [
        "users", "user_credits", "credit_transactions", "usage_history",
        "user_reports", "email_verification_tokens", "password_reset_tokens",
        "refresh_tokens", "user_files", "chat_sessions", "conversations",
        "chat_messages", "session_files", "pipelines", "pipeline_nodes",
        "pipeline_edges", "pipeline_executions", "pipeline_node_executions",
        "pipeline_node_files", "session_state", "three_d_canvases", "attachments",
        "admin_audit_log", "admin_preferences", "alphafold_jobs",
    ]
    
    print(f"  ✓ Created {len(tables)} tables")
    
    # Check for missing tables
    missing = [t for t in expected_tables if t not in tables]
    if missing:
        print(f"  ⚠ Warning: Missing tables: {missing}")
    else:
        print(f"  ✓ All {len(expected_tables)} expected tables are present\n")


def insert_test_user(conn: sqlite3.Connection) -> str:
    """Insert test user and return user_id."""
    print("Inserting test user...")
    
    # Generate user ID
    user_id = str(uuid.uuid4())
    email = "user1@gmail.com"
    username = "user1"
    password = "test12345"
    
    # Hash password
    password_hash = hash_password(password)
    
    # Insert user
    conn.execute(
        """INSERT INTO users (
            id, email, username, password_hash, user_type, role,
            email_verified, is_active, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            user_id,
            email,
            username,
            password_hash,
            "human",
            "user",
            1,  # email_verified
            1,  # is_active
            datetime.utcnow(),
            datetime.utcnow(),
        ),
    )
    
    print(f"  ✓ Created test user: {email} (username: {username})")
    print(f"  ✓ User ID: {user_id}")
    print(f"  ✓ Password: {password} (hashed)\n")
    
    return user_id


def insert_initial_credits(conn: sqlite3.Connection, user_id: str) -> None:
    """Insert initial credits for test user."""
    print("Inserting initial credits...")
    
    initial_credits = 1000
    
    conn.execute(
        """INSERT INTO user_credits (
            user_id, credits, total_earned, total_spent, updated_at
        ) VALUES (?, ?, ?, ?, ?)""",
        (
            user_id,
            initial_credits,
            initial_credits,  # total_earned
            0,  # total_spent
            datetime.utcnow(),
        ),
    )
    
    print(f"  ✓ Added {initial_credits} credits to user account\n")


def verify_schema(conn: sqlite3.Connection) -> bool:
    """Verify that all expected tables exist (must match schema.sql)."""
    print("Verifying database schema...")
    
    expected_tables = [
        "users", "user_credits", "credit_transactions", "usage_history",
        "user_reports", "email_verification_tokens", "password_reset_tokens",
        "refresh_tokens", "user_files", "chat_sessions", "conversations",
        "chat_messages", "session_files", "pipelines", "pipeline_nodes",
        "pipeline_edges", "pipeline_executions", "pipeline_node_executions",
        "pipeline_node_files", "session_state", "three_d_canvases", "attachments",
        "admin_audit_log", "admin_preferences", "alphafold_jobs",
    ]
    
    tables = get_all_tables(conn)
    
    missing = [t for t in expected_tables if t not in tables]
    extra = [t for t in tables if t not in expected_tables]
    
    if missing:
        print(f"  ✗ Missing tables: {missing}")
        return False
    
    if extra:
        print(f"  ⚠ Extra tables (not in expected list): {extra}")
    
    print(f"  ✓ All {len(expected_tables)} expected tables are present")
    
    # Verify test user exists
    user = conn.execute(
        "SELECT id, email, username FROM users WHERE email = ?",
        ("user1@gmail.com",)
    ).fetchone()
    
    if user:
        print(f"  ✓ Test user verified: {user['email']} (ID: {user['id']})")
    else:
        print("  ✗ Test user not found")
        return False
    
    # Verify credits exist
    credits = conn.execute(
        "SELECT credits FROM user_credits WHERE user_id = ?",
        (user['id'],)
    ).fetchone()
    
    if credits:
        print(f"  ✓ User credits verified: {credits['credits']} credits")
    else:
        print("  ✗ User credits not found")
        return False
    
    print()
    return True


def main():
    """Main seed script execution."""
    print("=" * 60)
    print("Database Seed Script")
    print("=" * 60)
    print()
    
    try:
        # Ensure database directory exists
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        with get_db() as conn:
            # Step 1: Drop all existing tables
            drop_all_tables(conn)
            
            # Step 2: Recreate schema from schema.sql
            recreate_schema(conn)
            
            # Step 3: Insert test user
            user_id = insert_test_user(conn)
            
            # Step 4: Insert initial credits
            insert_initial_credits(conn, user_id)
            
            # Step 5: Verify everything
            if verify_schema(conn):
                print("=" * 60)
                print("✓ Database seeded successfully!")
                print("=" * 60)
                print()
                print("Test user credentials:")
                print("  Email: user1@gmail.com")
                print("  Password: test12345")
                print("  Username: user1")
                print()
            else:
                print("=" * 60)
                print("⚠ Database seeded with warnings")
                print("=" * 60)
                sys.exit(1)
                
    except Exception as e:
        print(f"\n✗ Seed script failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
