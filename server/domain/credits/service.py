"""Credit system service."""

from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
import json

try:
    # Try relative import first (when running as module)
    from ...database.db import get_db
except ImportError:
    # Fallback to absolute import (when running directly)
    from database.db import get_db

# Credit costs for different actions
CREDIT_COSTS = {
    "alphafold": 50,
    "rfdiffusion": 75,
    "proteinmpnn": 25,
    "agent_chat": 1,
    "pipeline_execution": 100,  # Base cost, may vary by nodes
}


def get_user_credits(user_id: str) -> int:
    """Get current credit balance for user."""
    with get_db() as conn:
        result = conn.execute(
            "SELECT credits FROM user_credits WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        return result["credits"] if result else 0


def deduct_credits(
    user_id: str,
    amount: int,
    description: str,
    job_id: Optional[str] = None
) -> bool:
    """Deduct credits from user account. Returns True if successful, False if insufficient."""
    with get_db() as conn:
        # Check balance
        current_credits = get_user_credits(user_id)
        if current_credits < amount:
            return False
        
        # Deduct credits
        conn.execute(
            """UPDATE user_credits 
               SET credits = credits - ?, total_spent = total_spent + ?, updated_at = ?
               WHERE user_id = ?""",
            (amount, amount, datetime.utcnow(), user_id)
        )
        
        # Log transaction
        transaction_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO credit_transactions (id, user_id, amount, transaction_type, description, related_job_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (transaction_id, user_id, -amount, "spent", description, job_id)
        )
        
        return True


def add_credits(
    user_id: str,
    amount: int,
    description: str,
    transaction_type: str = "earned"
) -> None:
    """Add credits to user account with transaction logging."""
    with get_db() as conn:
        conn.execute(
            """UPDATE user_credits 
               SET credits = credits + ?, total_earned = total_earned + ?, updated_at = ?
               WHERE user_id = ?""",
            (amount, amount, datetime.utcnow(), user_id)
        )
        
        transaction_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO credit_transactions (id, user_id, amount, transaction_type, description)
               VALUES (?, ?, ?, ?, ?)""",
            (transaction_id, user_id, amount, transaction_type, description)
        )


def log_usage(
    user_id: str,
    action_type: str,
    credits_used: int,
    metadata: Dict[str, Any]
) -> None:
    """Log usage history with metadata."""
    usage_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            """INSERT INTO usage_history (id, user_id, action_type, resource_consumed, metadata)
               VALUES (?, ?, ?, ?, ?)""",
            (
                usage_id,
                user_id,
                action_type,
                json.dumps({"credits": credits_used}),
                json.dumps(metadata)
            )
        )


def get_credit_history(user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Get credit transaction history for user."""
    with get_db() as conn:
        transactions = conn.execute(
            """SELECT * FROM credit_transactions 
               WHERE user_id = ? 
               ORDER BY created_at DESC 
               LIMIT ?""",
            (user_id, limit)
        ).fetchall()
        return [dict(t) for t in transactions]


def get_usage_history(user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Get usage history for user."""
    with get_db() as conn:
        history = conn.execute(
            """SELECT * FROM usage_history 
               WHERE user_id = ? 
               ORDER BY created_at DESC 
               LIMIT ?""",
            (user_id, limit)
        ).fetchall()
        result = []
        for h in history:
            item = dict(h)
            # Parse JSON fields
            if item.get("resource_consumed"):
                item["resource_consumed"] = json.loads(item["resource_consumed"])
            if item.get("metadata"):
                item["metadata"] = json.loads(item["metadata"])
            result.append(item)
        return result

