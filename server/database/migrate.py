#!/usr/bin/env python3
"""
Database migration runner with history tracking.

Discovers and runs pending migrations from server/database/migrations/.
Tracks applied migrations in a `schema_migrations` table.

Usage:
    # From project root:
    python -m server.database.migrate

    # Or from server/ directory:
    python database/migrate.py
"""

import sqlite3
import importlib
import importlib.util
import sys
import types
from pathlib import Path
from datetime import datetime, timezone


def _get_db_path() -> Path:
    """Get the database path, matching db.py logic."""
    import os
    server_dir = Path(__file__).parent.parent

    # Try to import get_server_dir, with fallback
    try:
        from server.infrastructure.config import get_server_dir
        default_path = get_server_dir() / "novoprotein.db"
    except (ImportError, ModuleNotFoundError):
        default_path = server_dir / "novoprotein.db"

    return Path(os.getenv("DATABASE_PATH", str(default_path)))


def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    """Create the schema_migrations tracking table if it doesn't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
    """)
    conn.commit()


def _get_applied_versions(conn: sqlite3.Connection) -> set:
    """Return set of already-applied migration version strings."""
    cursor = conn.execute("SELECT version FROM schema_migrations ORDER BY version")
    return {row[0] for row in cursor.fetchall()}


def _discover_migrations(migrations_dir: Path) -> list:
    """Discover migration files sorted by version number.

    Expected naming: 001_description.py, 002_description.py, etc.
    Returns list of (version, name, path) tuples.
    """
    migrations = []
    for f in sorted(migrations_dir.glob("[0-9][0-9][0-9]_*.py")):
        version = f.stem[:3]  # "001", "002", etc.
        name = f.stem          # "001_user_isolation"
        migrations.append((version, name, f))
    return migrations


def _setup_mock_infrastructure():
    """Set up the mock infrastructure module that migrations need."""
    server_dir = Path(__file__).parent.parent

    infra_module = types.ModuleType('infrastructure')
    config_module = types.ModuleType('infrastructure.config')
    config_module.get_server_dir = lambda: server_dir
    infra_module.config = config_module
    sys.modules['infrastructure'] = infra_module
    sys.modules['infrastructure.config'] = config_module

    # Ensure server dir is in path for imports
    server_str = str(server_dir)
    if server_str not in sys.path:
        sys.path.insert(0, server_str)


def _load_migration_module(path: Path, name: str):
    """Dynamically load a migration module from file path."""
    spec = importlib.util.spec_from_file_location(f"migration_{name}", str(path))
    module = importlib.util.module_from_spec(spec)

    # Read source and patch the __main__ block so it doesn't auto-execute
    source = path.read_text(encoding="utf-8")
    source = source.replace('if __name__ == "__main__":', 'if False:  # disabled by runner')

    # Compile and run in module namespace
    code = compile(source, str(path), 'exec')

    # Note: We use exec() here intentionally to load migration modules
    # dynamically. The input is always from trusted local migration files,
    # never from user input or external sources.
    exec(code, module.__dict__)  # noqa: S102

    return module


def _run_single_migration(module, name: str) -> None:
    """Run the migration's entry point function."""
    # Try different entry point conventions used by existing migrations
    if hasattr(module, 'run_migration'):
        module.run_migration()
    elif hasattr(module, 'main'):
        module.main()
    elif hasattr(module, 'migrate_database_schema'):
        module.migrate_database_schema()
    else:
        raise RuntimeError(
            f"Migration {name} has no run_migration(), main(), or "
            f"migrate_database_schema() function"
        )


def run_migrations(db_path: Path = None, dry_run: bool = False) -> list:
    """Run all pending database migrations.

    Args:
        db_path: Path to SQLite database. Uses default if None.
        dry_run: If True, only report what would run without executing.

    Returns:
        List of applied migration version strings.
    """
    if db_path is None:
        db_path = _get_db_path()

    migrations_dir = Path(__file__).parent / "migrations"
    if not migrations_dir.exists():
        print("No migrations directory found.")
        return []

    # Setup mock infrastructure for migrations
    _setup_mock_infrastructure()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        _ensure_migrations_table(conn)
        applied = _get_applied_versions(conn)
        all_migrations = _discover_migrations(migrations_dir)

        pending = [(v, n, p) for v, n, p in all_migrations if v not in applied]

        if not pending:
            print(f"Database is up to date ({len(applied)} migrations applied)")
            return []

        print(f"Found {len(pending)} pending migration(s):")
        for version, name, _ in pending:
            print(f"  -> {name}")

        if dry_run:
            print("\n(dry run - no changes made)")
            return [v for v, _, _ in pending]

        applied_versions = []
        for version, name, path in pending:
            print(f"\n{'='*60}")
            print(f"Running migration: {name}")
            print(f"{'='*60}")

            try:
                module = _load_migration_module(path, name)
                _run_single_migration(module, name)

                # Record successful migration
                now = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                    (version, name, now)
                )
                conn.commit()

                applied_versions.append(version)
                print(f"Migration {name} applied successfully")

            except Exception as e:
                print(f"Migration {name} FAILED: {e}")
                conn.rollback()
                raise

        print(f"\nApplied {len(applied_versions)} migration(s) successfully")
        return applied_versions

    finally:
        conn.close()


def show_status(db_path: Path = None) -> None:
    """Show migration status - which are applied and which are pending."""
    if db_path is None:
        db_path = _get_db_path()

    migrations_dir = Path(__file__).parent / "migrations"

    if not db_path.exists():
        print(f"Database not found at {db_path}")
        print("Run init_db() first to create the database.")
        return

    conn = sqlite3.connect(str(db_path))
    try:
        _ensure_migrations_table(conn)
        applied = _get_applied_versions(conn)
        all_migrations = _discover_migrations(migrations_dir)

        cursor = conn.execute(
            "SELECT version, name, applied_at FROM schema_migrations ORDER BY version"
        )
        applied_rows = cursor.fetchall()

        print(f"Database: {db_path}")
        print(f"Total migrations: {len(all_migrations)}")
        print(f"Applied: {len(applied_rows)}")
        print(f"Pending: {len(all_migrations) - len(applied_rows)}")
        print()

        for version, name, _ in all_migrations:
            if version in applied:
                row = next(r for r in applied_rows if r[0] == version)
                print(f"  [applied] {name} ({row[2]})")
            else:
                print(f"  [pending] {name}")
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NovoProtein database migration runner")
    parser.add_argument("--status", action="store_true", help="Show migration status")
    parser.add_argument("--dry-run", action="store_true", help="Show pending without running")
    args = parser.parse_args()

    if args.status:
        show_status()
    else:
        run_migrations(dry_run=args.dry_run)
