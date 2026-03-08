"""Shared test fixtures for pipeline schema tests."""

import sqlite3
import json
import uuid
import pytest
from pathlib import Path
from datetime import datetime, timedelta, timezone


@pytest.fixture
def db():
    """In-memory SQLite database initialized with schema.sql."""
    schema_path = Path(__file__).parent.parent / "database" / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(schema_sql)
    yield conn
    conn.close()


@pytest.fixture
def user_id():
    """A deterministic test user ID."""
    return "test-user-001"


@pytest.fixture
def seed_user(db, user_id):
    """Insert a test user and return their ID."""
    db.execute(
        "INSERT INTO users (id, username, user_type, role) VALUES (?, ?, 'human', 'user')",
        (user_id, "testuser"),
    )
    db.commit()
    return user_id


@pytest.fixture
def other_user(db):
    """Insert a second user for access-control tests."""
    uid = "test-user-002"
    db.execute(
        "INSERT INTO users (id, username, user_type, role) VALUES (?, ?, 'human', 'user')",
        (uid, "otheruser"),
    )
    db.commit()
    return uid


def make_pipeline_id():
    return f"pipeline_{uuid.uuid4().hex[:12]}"


def make_node_id(prefix="node"):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def insert_pipeline(db, seed_user):
    """Factory fixture to insert a pipeline with nodes and edges."""

    def _insert(
        name="Test Pipeline",
        nodes=None,
        edges=None,
        status="draft",
        pipeline_id=None,
        user_id_override=None,
    ):
        pid = pipeline_id or make_pipeline_id()
        uid = user_id_override or seed_user
        now = datetime.now(timezone.utc).isoformat()

        db.execute(
            """INSERT INTO pipelines (id, user_id, name, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (pid, uid, name, status, now, now),
        )

        nodes = nodes or []
        for n in nodes:
            nid = n.get("id", make_node_id())
            n.setdefault("id", nid)
            db.execute(
                """INSERT INTO pipeline_nodes
                   (id, pipeline_id, type, label, config, inputs, status, result_metadata, error, position_x, position_y, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    nid, pid,
                    n.get("type", "input_node"),
                    n.get("label", "Node"),
                    json.dumps(n.get("config", {})),
                    json.dumps(n.get("inputs", {})),
                    n.get("status", "idle"),
                    json.dumps(n.get("result_metadata")) if n.get("result_metadata") else None,
                    n.get("error"),
                    n.get("position_x", 0),
                    n.get("position_y", 0),
                    now, now,
                ),
            )

        edges = edges or []
        for e in edges:
            db.execute(
                """INSERT INTO pipeline_edges (id, pipeline_id, source_node_id, target_node_id)
                   VALUES (?, ?, ?, ?)""",
                (str(uuid.uuid4()), pid, e["source"], e["target"]),
            )

        db.commit()
        return pid

    return _insert


@pytest.fixture
def insert_execution(db, seed_user):
    """Factory fixture to insert a pipeline execution with node executions."""

    def _insert(pipeline_id, node_logs=None, status="running", trigger_type="manual"):
        eid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        db.execute(
            """INSERT INTO pipeline_executions (id, pipeline_id, user_id, status, trigger_type, started_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (eid, pipeline_id, seed_user, status, trigger_type, now),
        )

        node_logs = node_logs or []
        ne_ids = []
        for order, log in enumerate(node_logs):
            ne_id = str(uuid.uuid4())
            ne_ids.append(ne_id)
            db.execute(
                """INSERT INTO pipeline_node_executions
                   (id, execution_id, node_id, pipeline_id, node_label, node_type,
                    status, execution_order, started_at, completed_at, duration_ms,
                    error, input_data, output_data,
                    request_method, request_url, request_headers, request_body,
                    response_status, response_status_text, response_headers, response_data)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ne_id, eid, log.get("node_id", ""), pipeline_id,
                    log.get("node_label", ""), log.get("node_type", ""),
                    log.get("status", "pending"), order,
                    log.get("started_at"), log.get("completed_at"),
                    log.get("duration_ms"),
                    log.get("error"),
                    json.dumps(log.get("input_data")) if log.get("input_data") else None,
                    json.dumps(log.get("output_data")) if log.get("output_data") else None,
                    log.get("request_method"), log.get("request_url"),
                    json.dumps(log.get("request_headers")) if log.get("request_headers") else None,
                    json.dumps(log.get("request_body")) if log.get("request_body") else None,
                    log.get("response_status"), log.get("response_status_text"),
                    json.dumps(log.get("response_headers")) if log.get("response_headers") else None,
                    json.dumps(log.get("response_data")) if log.get("response_data") else None,
                ),
            )

        db.commit()
        return eid, ne_ids

    return _insert
