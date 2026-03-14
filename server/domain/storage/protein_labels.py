"""Session-scoped protein label system (U1, P1, P2, …)."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime
from typing import Dict, List, Optional

try:
    from ...database.db import get_db
except ImportError:
    from database.db import get_db

_LABEL_RE = re.compile(r"^([A-Z]+)(\d+)$")
_DEFAULT_PREFIX = {"upload": "U"}


def _row_to_dict(row) -> Dict:
    """Convert sqlite3.Row to dict safely."""
    if isinstance(row, sqlite3.Row):
        return {key: row[key] for key in row.keys()}
    if isinstance(row, dict):
        return row
    return dict(row)


def generate_next_label(conn: sqlite3.Connection, session_id: str, prefix: str) -> str:
    """Return the next available label for *prefix* within *session_id*.

    E.g. if P1, P2, P4 exist the next label is P5.
    """
    rows = conn.execute(
        "SELECT short_label FROM protein_labels WHERE session_id = ? AND short_label LIKE ?",
        (session_id, f"{prefix}%"),
    ).fetchall()

    max_n = 0
    for row in rows:
        m = _LABEL_RE.match(row["short_label"] if isinstance(row, sqlite3.Row) else row[0])
        if m and m.group(1) == prefix:
            max_n = max(max_n, int(m.group(2)))
    return f"{prefix}{max_n + 1}"


def register_protein_label(
    session_id: str,
    user_id: str,
    kind: str,
    source_tool: str | None = None,
    file_id: str | None = None,
    job_id: str | None = None,
    metadata: dict | None = None,
    preferred_prefix: str | None = None,
) -> Dict:
    """Create a new protein label and return the row as a dict.

    Automatically generates the next sequential label within the session.
    Retries up to 3 times on uniqueness collisions.
    """
    prefix = preferred_prefix or _DEFAULT_PREFIX.get(kind, "P")

    with get_db() as conn:
        session = conn.execute(
            "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        if not session:
            raise ValueError(f"Session {session_id} not found or access denied")

        if file_id:
            file_row = conn.execute(
                "SELECT id FROM user_files WHERE id = ? AND user_id = ?",
                (file_id, user_id),
            ).fetchone()
            if not file_row:
                raise ValueError(f"File {file_id} not found or access denied")

        metadata_json = json.dumps(metadata) if metadata else None
        now = datetime.utcnow().isoformat()

        for _ in range(3):
            short_label = generate_next_label(conn, session_id, prefix)
            label_id = str(uuid.uuid4())
            try:
                conn.execute(
                    """INSERT INTO protein_labels
                       (id, user_id, session_id, short_label, kind, source_tool,
                        file_id, job_id, metadata, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (label_id, user_id, session_id, short_label, kind, source_tool,
                     file_id, job_id, metadata_json, now, now),
                )
                row = conn.execute(
                    "SELECT * FROM protein_labels WHERE id = ?", (label_id,)
                ).fetchone()
                return _row_to_dict(row)
            except sqlite3.IntegrityError:
                continue

        raise RuntimeError("Failed to generate a unique protein label after retries")


def get_protein_labels_for_session(session_id: str, user_id: str) -> List[Dict]:
    """Return all protein labels for a session owned by user_id."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM protein_labels
               WHERE session_id = ? AND user_id = ?
               ORDER BY created_at ASC""",
            (session_id, user_id),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


def get_protein_label_by_short_label(
    session_id: str, user_id: str, short_label: str
) -> Optional[Dict]:
    """Lookup a single label by its short_label within a session."""
    with get_db() as conn:
        row = conn.execute(
            """SELECT * FROM protein_labels
               WHERE session_id = ? AND user_id = ? AND short_label = ?""",
            (session_id, user_id, short_label),
        ).fetchone()
        return _row_to_dict(row) if row else None


def get_protein_label_by_id(label_id: str, user_id: str) -> Optional[Dict]:
    """Lookup a protein label by its primary key."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM protein_labels WHERE id = ? AND user_id = ?",
            (label_id, user_id),
        ).fetchone()
        return _row_to_dict(row) if row else None
