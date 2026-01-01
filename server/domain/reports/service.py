"""User reporting system service."""

from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

from ...database.db import get_db


def create_report(
    user_id: str,
    report_type: str,
    title: str,
    description: str
) -> Dict[str, Any]:
    """Create a new user report."""
    report_id = str(uuid.uuid4())
    
    with get_db() as conn:
        conn.execute(
            """INSERT INTO user_reports (id, user_id, report_type, title, description, status, priority)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (report_id, user_id, report_type, title, description, "pending", "medium")
        )
    
    return {"report_id": report_id, "message": "Report submitted successfully"}


def get_user_reports(user_id: str) -> List[Dict[str, Any]]:
    """Get all reports by a user."""
    with get_db() as conn:
        reports = conn.execute(
            """SELECT * FROM user_reports WHERE user_id = ? ORDER BY created_at DESC""",
            (user_id,)
        ).fetchall()
        return [dict(r) for r in reports]


def get_all_reports(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get all reports (admin only), optionally filtered by status."""
    with get_db() as conn:
        if status:
            reports = conn.execute(
                """SELECT r.*, u.username, u.email 
                   FROM user_reports r
                   JOIN users u ON r.user_id = u.id
                   WHERE r.status = ? ORDER BY r.created_at DESC""",
                (status,)
            ).fetchall()
        else:
            reports = conn.execute(
                """SELECT r.*, u.username, u.email 
                   FROM user_reports r
                   JOIN users u ON r.user_id = u.id
                   ORDER BY r.created_at DESC""",
            ).fetchall()
        return [dict(r) for r in reports]


def update_report_status(
    report_id: str,
    status: str,
    admin_id: str,
    notes: Optional[str] = None,
    priority: Optional[str] = None
) -> None:
    """Update report status (admin only)."""
    with get_db() as conn:
        update_fields = ["status = ?", "assigned_admin_id = ?", "updated_at = ?"]
        update_values = [status, admin_id, datetime.utcnow()]
        
        if notes is not None:
            update_fields.append("admin_notes = ?")
            update_values.append(notes)
        
        if priority is not None:
            update_fields.append("priority = ?")
            update_values.append(priority)
        
        update_values.append(report_id)
        
        conn.execute(
            f"""UPDATE user_reports 
               SET {', '.join(update_fields)}
               WHERE id = ?""",
            update_values
        )


def get_report_by_id(report_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific report by ID."""
    with get_db() as conn:
        report = conn.execute(
            """SELECT r.*, u.username, u.email 
               FROM user_reports r
               JOIN users u ON r.user_id = u.id
               WHERE r.id = ?""",
            (report_id,)
        ).fetchone()
        return dict(report) if report else None

