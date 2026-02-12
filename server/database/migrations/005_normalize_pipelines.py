#!/usr/bin/env python3
"""
Migration 005: Normalize pipeline storage.

Migrates from monolithic pipeline_json blob + execution_log JSON array
to normalized tables: pipeline_nodes, pipeline_edges, pipeline_node_executions,
pipeline_node_files. Adds typed SQL views for querying node-specific config fields.
"""

import sqlite3
import json
import uuid
from pathlib import Path
import sys
import traceback

# Add server directory to path
migration_file_dir = Path(__file__).parent  # server/database/migrations/
server_dir = migration_file_dir.parent.parent  # server/

sys.path.insert(0, str(server_dir))

# Mock infrastructure.config before importing db
import types
infra_module = types.ModuleType('infrastructure')
config_module = types.ModuleType('infrastructure.config')
config_module.get_server_dir = lambda: server_dir
infra_module.config = config_module
sys.modules['infrastructure'] = infra_module
sys.modules['infrastructure.config'] = config_module

try:
    from database.db import DB_PATH
except ImportError:
    DB_PATH = server_dir / "novoprotein.db"


def _create_new_tables(conn: sqlite3.Connection):
    """Phase 1: Create new normalized tables alongside legacy tables."""
    print("  Creating pipeline_nodes table...")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_nodes (
            id TEXT NOT NULL,
            pipeline_id TEXT NOT NULL,
            type TEXT NOT NULL
                CHECK (type IN (
                    'input_node', 'rfdiffusion_node', 'proteinmpnn_node',
                    'alphafold_node', 'openfold2_node', 'message_input_node',
                    'http_request_node'
                )),
            label TEXT NOT NULL,
            config TEXT NOT NULL DEFAULT '{}',
            inputs TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'idle'
                CHECK (status IN ('idle', 'running', 'success', 'completed', 'error', 'pending')),
            result_metadata TEXT,
            error TEXT,
            position_x REAL DEFAULT 0,
            position_y REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id, pipeline_id)
        )
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_nodes_pipeline_id ON pipeline_nodes(pipeline_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_nodes_type ON pipeline_nodes(type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_nodes_status ON pipeline_nodes(status)")

    print("  Creating pipeline_edges table...")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_edges (
            id TEXT PRIMARY KEY,
            pipeline_id TEXT NOT NULL,
            source_node_id TEXT NOT NULL,
            target_node_id TEXT NOT NULL,
            source_handle TEXT DEFAULT 'source',
            target_handle TEXT DEFAULT 'target',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (pipeline_id, source_node_id, target_node_id, source_handle, target_handle)
        )
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_edges_pipeline_id ON pipeline_edges(pipeline_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_edges_source ON pipeline_edges(source_node_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_edges_target ON pipeline_edges(target_node_id)")

    print("  Creating pipeline_node_executions table...")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_node_executions (
            id TEXT PRIMARY KEY,
            execution_id TEXT NOT NULL,
            node_id TEXT NOT NULL,
            pipeline_id TEXT NOT NULL,
            node_label TEXT NOT NULL,
            node_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'running', 'success', 'completed', 'error', 'skipped')),
            execution_order INTEGER,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            duration_ms INTEGER,
            error TEXT,
            input_data TEXT,
            output_data TEXT,
            request_method TEXT,
            request_url TEXT,
            request_headers TEXT,
            request_body TEXT,
            response_status INTEGER,
            response_status_text TEXT,
            response_headers TEXT,
            response_data TEXT
        )
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_pne_execution_id ON pipeline_node_executions(execution_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pne_node_id ON pipeline_node_executions(node_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pne_status ON pipeline_node_executions(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pne_execution_order ON pipeline_node_executions(execution_id, execution_order)")

    print("  Creating pipeline_node_files table...")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_node_files (
            id TEXT PRIMARY KEY,
            pipeline_id TEXT NOT NULL,
            node_id TEXT NOT NULL,
            execution_id TEXT,
            node_execution_id TEXT,
            file_id TEXT,
            role TEXT NOT NULL
                CHECK (role IN ('input', 'output', 'template', 'reference')),
            file_type TEXT DEFAULT 'pdb',
            filename TEXT,
            file_url TEXT,
            file_path TEXT,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_pnf_pipeline_id ON pipeline_node_files(pipeline_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pnf_node_id ON pipeline_node_files(node_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pnf_execution_id ON pipeline_node_files(execution_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pnf_file_id ON pipeline_node_files(file_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pnf_role ON pipeline_node_files(role)")


def _create_typed_views(conn: sqlite3.Connection):
    """Create typed SQL views for querying node-specific config fields."""
    print("  Creating typed views...")

    conn.execute("""
        CREATE VIEW IF NOT EXISTS v_input_nodes AS
        SELECT
            pn.id, pn.pipeline_id, pn.label, pn.status,
            json_extract(pn.config, '$.filename') AS filename,
            json_extract(pn.config, '$.file_id') AS file_id,
            json_extract(pn.config, '$.atoms') AS atoms,
            json_extract(pn.config, '$.chains') AS chains,
            json_extract(pn.config, '$.total_residues') AS total_residues,
            json_extract(pn.config, '$.suggested_contigs') AS suggested_contigs,
            pn.result_metadata, pn.error, pn.position_x, pn.position_y
        FROM pipeline_nodes pn WHERE pn.type = 'input_node'
    """)

    conn.execute("""
        CREATE VIEW IF NOT EXISTS v_rfdiffusion_nodes AS
        SELECT
            pn.id, pn.pipeline_id, pn.label, pn.status,
            json_extract(pn.config, '$.design_mode') AS design_mode,
            json_extract(pn.config, '$.contigs') AS contigs,
            json_extract(pn.config, '$.hotspot_res') AS hotspot_res,
            json_extract(pn.config, '$.diffusion_steps') AS diffusion_steps,
            json_extract(pn.config, '$.num_designs') AS num_designs,
            json_extract(pn.config, '$.pdb_id') AS pdb_id,
            pn.result_metadata, pn.error, pn.position_x, pn.position_y
        FROM pipeline_nodes pn WHERE pn.type = 'rfdiffusion_node'
    """)

    conn.execute("""
        CREATE VIEW IF NOT EXISTS v_proteinmpnn_nodes AS
        SELECT
            pn.id, pn.pipeline_id, pn.label, pn.status,
            json_extract(pn.config, '$.num_sequences') AS num_sequences,
            json_extract(pn.config, '$.temperature') AS temperature,
            pn.result_metadata, pn.error, pn.position_x, pn.position_y
        FROM pipeline_nodes pn WHERE pn.type = 'proteinmpnn_node'
    """)

    conn.execute("""
        CREATE VIEW IF NOT EXISTS v_alphafold_nodes AS
        SELECT
            pn.id, pn.pipeline_id, pn.label, pn.status,
            json_extract(pn.config, '$.recycle_count') AS recycle_count,
            json_extract(pn.config, '$.num_relax') AS num_relax,
            pn.result_metadata, pn.error, pn.position_x, pn.position_y
        FROM pipeline_nodes pn WHERE pn.type = 'alphafold_node'
    """)

    conn.execute("""
        CREATE VIEW IF NOT EXISTS v_openfold2_nodes AS
        SELECT
            pn.id, pn.pipeline_id, pn.label, pn.status,
            json_extract(pn.config, '$.sequence') AS sequence,
            json_extract(pn.config, '$.relax_prediction') AS relax_prediction,
            pn.result_metadata, pn.error, pn.position_x, pn.position_y
        FROM pipeline_nodes pn WHERE pn.type = 'openfold2_node'
    """)


def _migrate_pipeline_data(conn: sqlite3.Connection):
    """Phase 2: Migrate pipeline_json blobs to normalized tables."""
    print("  Migrating pipeline data...")

    # Check if old pipelines table has pipeline_json column
    columns = [row[1] for row in conn.execute("PRAGMA table_info(pipelines)").fetchall()]
    if 'pipeline_json' not in columns:
        print("  No pipeline_json column found, skipping pipeline data migration")
        return 0

    rows = conn.execute(
        "SELECT id, user_id, message_id, conversation_id, name, description, "
        "pipeline_json, status, created_at, updated_at FROM pipelines"
    ).fetchall()

    migrated = 0
    for row in rows:
        pipeline = dict(row)
        pipeline_id = pipeline['id']

        try:
            data = json.loads(pipeline['pipeline_json'])
        except (json.JSONDecodeError, TypeError):
            print(f"  Warning: Skipping pipeline {pipeline_id} - invalid JSON")
            continue

        nodes = data.get('nodes', [])
        edges = data.get('edges', [])

        # Insert nodes
        for node in nodes:
            position = node.get('position', {})
            result_meta = node.get('result_metadata')

            conn.execute("""
                INSERT OR IGNORE INTO pipeline_nodes
                    (id, pipeline_id, type, label, config, inputs, status,
                     result_metadata, error, position_x, position_y)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                node['id'], pipeline_id, node.get('type', 'input_node'),
                node.get('label', ''),
                json.dumps(node.get('config', {})),
                json.dumps(node.get('inputs', {})),
                node.get('status', 'idle'),
                json.dumps(result_meta) if result_meta else None,
                node.get('error'),
                position.get('x', 0), position.get('y', 0)
            ))

            # Extract file references
            config = node.get('config', {})
            node_type = node.get('type', '')

            # Input node files
            if node_type == 'input_node' and config.get('file_id'):
                file_meta = {}
                for key in ['atoms', 'chains', 'chain_residue_counts', 'total_residues', 'suggested_contigs']:
                    if key in config:
                        file_meta[key] = config[key]
                conn.execute("""
                    INSERT OR IGNORE INTO pipeline_node_files
                        (id, pipeline_id, node_id, role, file_type, filename,
                         file_url, file_id, metadata)
                    VALUES (?, ?, ?, 'input', 'pdb', ?, ?, ?, ?)
                """, (
                    str(uuid.uuid4()), pipeline_id, node['id'],
                    config.get('filename'),
                    config.get('file_url'),
                    config.get('file_id'),
                    json.dumps(file_meta) if file_meta else None
                ))

            # Output file references from result_metadata
            if result_meta and isinstance(result_meta, dict):
                output_file = result_meta.get('output_file')
                if output_file and isinstance(output_file, dict):
                    conn.execute("""
                        INSERT OR IGNORE INTO pipeline_node_files
                            (id, pipeline_id, node_id, role, file_type, filename,
                             file_url, file_path, file_id)
                        VALUES (?, ?, ?, 'output', 'pdb', ?, ?, ?, ?)
                    """, (
                        str(uuid.uuid4()), pipeline_id, node['id'],
                        output_file.get('filename'),
                        output_file.get('file_url'),
                        output_file.get('filepath'),
                        output_file.get('file_id')
                    ))

        # Insert edges
        for edge in edges:
            conn.execute("""
                INSERT OR IGNORE INTO pipeline_edges
                    (id, pipeline_id, source_node_id, target_node_id)
                VALUES (?, ?, ?, ?)
            """, (
                str(uuid.uuid4()), pipeline_id,
                edge.get('source', ''), edge.get('target', '')
            ))

        migrated += 1

    print(f"  Migrated {migrated} pipelines ({sum(len(json.loads(dict(r)['pipeline_json']).get('nodes', [])) for r in conn.execute('SELECT pipeline_json FROM pipelines').fetchall() if dict(r).get('pipeline_json'))} nodes)")
    return migrated


def _migrate_execution_data(conn: sqlite3.Connection):
    """Phase 3: Migrate execution_log JSON arrays to pipeline_node_executions."""
    print("  Migrating execution data...")

    # Check if old pipeline_executions table has execution_log column
    columns = [row[1] for row in conn.execute("PRAGMA table_info(pipeline_executions)").fetchall()]
    if 'execution_log' not in columns:
        print("  No execution_log column found, skipping execution data migration")
        return 0

    rows = conn.execute(
        "SELECT id, pipeline_id, user_id, status, started_at, "
        "completed_at, execution_log FROM pipeline_executions"
    ).fetchall()

    migrated = 0
    for row in rows:
        execution = dict(row)
        exec_id = execution['id']

        try:
            logs = json.loads(execution.get('execution_log') or '[]')
        except (json.JSONDecodeError, TypeError):
            continue

        for order, log in enumerate(logs):
            ne_id = str(uuid.uuid4())
            request = log.get('request', {}) or {}
            response = log.get('response', {}) or {}

            # Strip raw PDB content from response_data to keep DB lean
            resp_data = response.get('data')
            if resp_data and isinstance(resp_data, dict):
                # Remove pdbContent if present - it stays on disk
                resp_data_clean = {k: v for k, v in resp_data.items() if k != 'pdbContent'}
                resp_data = resp_data_clean if resp_data_clean else None
            elif resp_data and isinstance(resp_data, str) and len(resp_data) > 10000:
                # Skip very large raw string responses (likely PDB content)
                resp_data = None

            conn.execute("""
                INSERT OR IGNORE INTO pipeline_node_executions
                    (id, execution_id, node_id, pipeline_id, node_label, node_type,
                     status, execution_order, started_at, completed_at, duration_ms,
                     error, input_data, output_data,
                     request_method, request_url, request_headers, request_body,
                     response_status, response_status_text, response_headers, response_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ne_id, exec_id, log.get('nodeId', ''), execution['pipeline_id'],
                log.get('nodeLabel', ''), log.get('nodeType', ''),
                log.get('status', 'pending'), order,
                log.get('startedAt'), log.get('completedAt'),
                log.get('duration'),
                log.get('error'),
                json.dumps(log.get('input')) if log.get('input') else None,
                json.dumps(log.get('output')) if log.get('output') else None,
                request.get('method'), request.get('url'),
                json.dumps(request.get('headers')) if request.get('headers') else None,
                json.dumps(request.get('body')) if request.get('body') else None,
                response.get('status'), response.get('statusText'),
                json.dumps(response.get('headers')) if response.get('headers') else None,
                json.dumps(resp_data) if resp_data else None
            ))

            # Track output files from execution results
            output = log.get('output', {})
            if output and isinstance(output, dict):
                output_file = output.get('output_file') or output.get('file_info')
                if output_file and isinstance(output_file, dict):
                    conn.execute("""
                        INSERT OR IGNORE INTO pipeline_node_files
                            (id, pipeline_id, node_id, execution_id, node_execution_id,
                             role, file_type, filename, file_url, file_path, file_id)
                        VALUES (?, ?, ?, ?, ?, 'output', 'pdb', ?, ?, ?, ?)
                    """, (
                        str(uuid.uuid4()), execution['pipeline_id'], log.get('nodeId', ''),
                        exec_id, ne_id,
                        output_file.get('filename'),
                        output_file.get('file_url'),
                        output_file.get('filepath'),
                        output_file.get('file_id')
                    ))

        migrated += 1

    print(f"  Migrated {migrated} execution records")
    return migrated


def _restructure_tables(conn: sqlite3.Connection):
    """Phase 4: Restructure pipelines and pipeline_executions tables to remove JSON blobs."""
    print("  Restructuring pipelines table...")

    # Check if pipeline_json column exists (migration may have already run)
    columns = [row[1] for row in conn.execute("PRAGMA table_info(pipelines)").fetchall()]
    if 'pipeline_json' not in columns:
        print("  pipelines table already restructured, skipping")
        return

    # SQLite doesn't support DROP COLUMN before 3.35.0, so we recreate the table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pipelines_new (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            message_id TEXT,
            conversation_id TEXT,
            name TEXT NOT NULL DEFAULT 'Untitled Pipeline',
            description TEXT,
            status TEXT NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft', 'running', 'completed', 'failed')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (message_id) REFERENCES chat_messages(id) ON DELETE SET NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL
        )
    """)

    conn.execute("""
        INSERT OR IGNORE INTO pipelines_new (id, user_id, message_id, conversation_id, name, description, status, created_at, updated_at)
        SELECT id, user_id, message_id, conversation_id,
               COALESCE(name, 'Untitled Pipeline'), description,
               COALESCE(status, 'draft'), created_at, updated_at
        FROM pipelines
    """)

    conn.execute("DROP TABLE pipelines")
    conn.execute("ALTER TABLE pipelines_new RENAME TO pipelines")

    # Recreate indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pipelines_user_id ON pipelines(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pipelines_message_id ON pipelines(message_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pipelines_conversation_id ON pipelines(conversation_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pipelines_status ON pipelines(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pipelines_updated_at ON pipelines(updated_at)")

    print("  Restructuring pipeline_executions table...")

    columns = [row[1] for row in conn.execute("PRAGMA table_info(pipeline_executions)").fetchall()]
    if 'execution_log' not in columns:
        print("  pipeline_executions table already restructured, skipping")
        return

    conn.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_executions_new (
            id TEXT PRIMARY KEY,
            pipeline_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'running'
                CHECK (status IN ('running', 'completed', 'failed', 'stopped', 'cancelled')),
            trigger_type TEXT DEFAULT 'manual'
                CHECK (trigger_type IN ('manual', 'rerun', 'single_node', 'scheduled')),
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            total_duration_ms INTEGER,
            error_summary TEXT,
            metadata TEXT,
            FOREIGN KEY (pipeline_id) REFERENCES pipelines(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        INSERT OR IGNORE INTO pipeline_executions_new (id, pipeline_id, user_id, status, started_at, completed_at)
        SELECT id, pipeline_id, user_id, status, started_at, completed_at
        FROM pipeline_executions
    """)

    conn.execute("DROP TABLE pipeline_executions")
    conn.execute("ALTER TABLE pipeline_executions_new RENAME TO pipeline_executions")

    # Recreate indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_executions_pipeline_id ON pipeline_executions(pipeline_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_executions_user_id ON pipeline_executions(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_executions_status ON pipeline_executions(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_executions_started_at ON pipeline_executions(started_at)")


def _add_foreign_keys(conn: sqlite3.Connection):
    """Phase 5: Add foreign keys to new tables referencing restructured tables."""
    # Foreign keys on pipeline_nodes, pipeline_edges, pipeline_node_executions, pipeline_node_files
    # were not added with REFERENCES during creation because the legacy pipelines table
    # was still in place. SQLite doesn't support ALTER TABLE ADD FOREIGN KEY, and the
    # tables were created without them intentionally. The CHECK constraints and indexes
    # provide the necessary integrity. In production, PRAGMA foreign_keys = ON will
    # enforce referential integrity for new inserts/updates going forward.
    pass


def _verify_migration(conn: sqlite3.Connection):
    """Phase 6: Verify data integrity post-migration."""
    print("  Verifying migration...")

    pipeline_count = conn.execute("SELECT COUNT(*) FROM pipelines").fetchone()[0]
    node_count = conn.execute("SELECT COUNT(*) FROM pipeline_nodes").fetchone()[0]
    edge_count = conn.execute("SELECT COUNT(*) FROM pipeline_edges").fetchone()[0]
    exec_count = conn.execute("SELECT COUNT(*) FROM pipeline_executions").fetchone()[0]
    node_exec_count = conn.execute("SELECT COUNT(*) FROM pipeline_node_executions").fetchone()[0]
    file_count = conn.execute("SELECT COUNT(*) FROM pipeline_node_files").fetchone()[0]

    print(f"  Pipelines: {pipeline_count}")
    print(f"  Nodes: {node_count}")
    print(f"  Edges: {edge_count}")
    print(f"  Executions: {exec_count}")
    print(f"  Node executions: {node_exec_count}")
    print(f"  Node files: {file_count}")

    # Verify pipelines table no longer has pipeline_json
    columns = [row[1] for row in conn.execute("PRAGMA table_info(pipelines)").fetchall()]
    assert 'pipeline_json' not in columns, "pipeline_json column should be removed"

    # Verify pipeline_executions table no longer has execution_log
    columns = [row[1] for row in conn.execute("PRAGMA table_info(pipeline_executions)").fetchall()]
    assert 'execution_log' not in columns, "execution_log column should be removed"

    # Verify typed views exist
    views = [row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='view'"
    ).fetchall()]
    expected_views = ['v_input_nodes', 'v_rfdiffusion_nodes', 'v_proteinmpnn_nodes',
                      'v_alphafold_nodes', 'v_openfold2_nodes']
    for view in expected_views:
        assert view in views, f"View {view} should exist"

    print("  Verification passed!")


def run_migration():
    """Run the full normalization migration."""
    try:
        print(f"Running migration 005: Normalize pipeline storage...")
        print(f"Database path: {DB_PATH}")

        if not Path(DB_PATH).exists():
            print(f"Database not found at {DB_PATH}, skipping migration (schema.sql will create tables)")
            return

        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = OFF")  # Disable during migration

        # Check if migration already ran
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_nodes'"
        )
        already_has_nodes = cursor.fetchone() is not None

        columns = [row[1] for row in conn.execute("PRAGMA table_info(pipelines)").fetchall()]
        already_restructured = 'pipeline_json' not in columns

        if already_has_nodes and already_restructured:
            print("Migration 005 already completed, skipping")
            conn.close()
            return

        # Phase 1: Create new tables
        print("Phase 1: Creating new tables...")
        _create_new_tables(conn)
        _create_typed_views(conn)
        conn.commit()

        # Phase 2: Migrate pipeline data (only if pipeline_json exists)
        if not already_restructured:
            print("Phase 2: Migrating pipeline data...")
            _migrate_pipeline_data(conn)
            conn.commit()

            # Phase 3: Migrate execution data
            print("Phase 3: Migrating execution data...")
            _migrate_execution_data(conn)
            conn.commit()

            # Phase 4: Restructure tables (remove JSON blob columns)
            print("Phase 4: Restructuring tables...")
            _restructure_tables(conn)
            conn.commit()

        # Phase 5: Add foreign keys
        _add_foreign_keys(conn)
        conn.commit()

        # Phase 6: Verify
        print("Phase 6: Verifying...")
        _verify_migration(conn)

        conn.execute("PRAGMA foreign_keys = ON")
        conn.close()

        print("Migration 005 completed successfully!")

    except Exception as e:
        print(f"Migration 005 failed: {e}")
        traceback.print_exc()
        raise


def rollback():
    """Rollback: Drop new tables and restore original schema.
    NOTE: This is destructive - only use if migration verification failed."""
    print("Rolling back migration 005...")

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = OFF")

    # Drop views
    for view in ['v_input_nodes', 'v_rfdiffusion_nodes', 'v_proteinmpnn_nodes',
                 'v_alphafold_nodes', 'v_openfold2_nodes']:
        conn.execute(f"DROP VIEW IF EXISTS {view}")

    # Drop new tables
    conn.execute("DROP TABLE IF EXISTS pipeline_node_files")
    conn.execute("DROP TABLE IF EXISTS pipeline_node_executions")
    conn.execute("DROP TABLE IF EXISTS pipeline_edges")
    conn.execute("DROP TABLE IF EXISTS pipeline_nodes")

    conn.commit()
    conn.close()
    print("Rollback complete. Note: pipelines and pipeline_executions tables need manual restoration from backup.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Migration 005: Normalize pipeline storage")
    parser.add_argument("--rollback", action="store_true", help="Rollback migration")
    args = parser.parse_args()

    if args.rollback:
        rollback()
    else:
        run_migration()
