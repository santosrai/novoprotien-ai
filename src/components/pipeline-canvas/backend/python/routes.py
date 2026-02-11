"""
Pluggable FastAPI router for pipeline persistence.
Inject get_db and get_current_user from your host application.
Supports both authenticated and unauthenticated (no-auth) modes.
"""
from typing import Dict, Any, List, Optional, Callable, Literal
from fastapi import APIRouter, HTTPException, Depends, status, Request
import json
import uuid
from datetime import datetime


def create_pipeline_router(
    get_db: Callable,
    get_current_user: Optional[Callable] = None,
    *,
    auth_mode: Literal["required", "optional", "disabled"] = "required",
    get_current_user_optional: Optional[Callable] = None,
    session_header: str = "X-Session-Id",
    anonymous_id: str = "anonymous",
    verify_message_ownership: bool = False,
) -> APIRouter:
    """
    Create a FastAPI router for pipeline persistence.

    Args:
        get_db: Context manager yielding a DB connection (e.g., sqlite3 connection).
                Must support: with get_db() as conn: conn.execute(...)
        get_current_user: FastAPI dependency that returns {"id": user_id, ...}.
                Required when auth_mode is "required". Ignored for "disabled".
        auth_mode: "required" = must be authenticated (default, backwards compatible).
                   "optional" = use user when present (via get_current_user_optional), else session/anonymous.
                   "disabled" = never require auth; always use session/anonymous.
        get_current_user_optional: For auth_mode "optional": dependency that returns user or None.
                Use HTTPBearer(auto_error=False) to avoid 401 when no token.
        session_header: HTTP header name for session scope when no auth (default: X-Session-Id).
        anonymous_id: Fallback scope when no user and no session header (default: "anonymous").
        verify_message_ownership: If True, verify message_id and conversation_id
                against chat_messages/conversations/chat_sessions tables.
                Set False if your app has no chat tables.

    Returns:
        APIRouter with prefix /api/pipelines
    """
    if auth_mode == "required" and get_current_user is None:
        raise ValueError("get_current_user is required when auth_mode is 'required'")

    router = APIRouter(prefix="/api/pipelines", tags=["pipelines"])

    # Build the user-resolver dependency based on auth_mode
    if auth_mode == "disabled":
        async def _resolve_user(request: Request) -> Dict[str, Any]:
            uid = request.headers.get(session_header) or anonymous_id
            return {"id": uid}
    elif auth_mode == "optional" and get_current_user_optional is not None:
        async def _resolve_user(
            request: Request,
            user: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
        ) -> Dict[str, Any]:
            if user and user.get("id"):
                return user
            uid = request.headers.get(session_header) or anonymous_id
            return {"id": uid}
    elif auth_mode == "optional":
        # No optional dep provided: use session/anonymous only
        async def _resolve_user(request: Request) -> Dict[str, Any]:
            uid = request.headers.get(session_header) or anonymous_id
            return {"id": uid}
    else:
        # required: use get_current_user directly
        _resolve_user = get_current_user

    def _verify_message(conn, message_id: str, user_id: str) -> Optional[str]:
        if not verify_message_ownership or not message_id:
            return message_id
        row = conn.execute(
            "SELECT id, conversation_id, session_id FROM chat_messages WHERE id = ? AND user_id = ?",
            (message_id, user_id),
        ).fetchone()
        if not row:
            return None
        return message_id

    def _verify_conversation(conn, conversation_id: str, user_id: str) -> bool:
        if not verify_message_ownership or not conversation_id:
            return True
        row = conn.execute(
            "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        ).fetchone()
        if row:
            return True
        row = conn.execute(
            "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        ).fetchone()
        return row is not None

    @router.post("")
    async def create_pipeline(
        pipeline_data: Dict[str, Any],
        user: Dict[str, Any] = Depends(_resolve_user),
    ) -> Dict[str, Any]:
        """Create or save a pipeline."""
        pipeline_id = pipeline_data.get("id") or str(uuid.uuid4())
        name = pipeline_data.get("name", "Untitled Pipeline")
        description = pipeline_data.get("description")
        pipeline_json = json.dumps(pipeline_data)
        status_value = pipeline_data.get("status", "draft")
        message_id = pipeline_data.get("message_id")
        conversation_id = pipeline_data.get("conversation_id")

        with get_db() as conn:
            if verify_message_ownership:
                if message_id:
                    msg = _verify_message(conn, message_id, user["id"])
                    if not msg:
                        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found or access denied")
                    row = conn.execute(
                        "SELECT conversation_id, session_id FROM chat_messages WHERE id = ?",
                        (message_id,),
                    ).fetchone()
                    if row and not conversation_id:
                        r = dict(row)
                        conversation_id = r.get("conversation_id") or r.get("session_id")
                if conversation_id and not _verify_conversation(conn, conversation_id, user["id"]):
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found or access denied")

            existing = conn.execute(
                "SELECT id FROM pipelines WHERE id = ? AND user_id = ?",
                (pipeline_id, user["id"]),
            ).fetchone()

            if existing:
                updates = ["name = ?", "description = ?", "pipeline_json = ?", "status = ?", "updated_at = ?"]
                params = [name, description, pipeline_json, status_value, datetime.utcnow()]
                if message_id is not None:
                    updates.append("message_id = ?")
                    params.append(message_id)
                if conversation_id is not None:
                    updates.append("conversation_id = ?")
                    params.append(conversation_id)
                params.extend([pipeline_id, user["id"]])
                conn.execute(
                    f"UPDATE pipelines SET {', '.join(updates)} WHERE id = ? AND user_id = ?",
                    params,
                )
            else:
                conn.execute(
                    """INSERT INTO pipelines
                       (id, user_id, message_id, conversation_id, name, description, pipeline_json, status, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        pipeline_id,
                        user["id"],
                        message_id,
                        conversation_id,
                        name,
                        description,
                        pipeline_json,
                        status_value,
                        datetime.utcnow(),
                        datetime.utcnow(),
                    ),
                )
            conn.commit()

        return {
            "status": "success",
            "pipeline": {"id": pipeline_id},
            "pipeline_id": pipeline_id,
            "message": "Pipeline saved successfully",
        }

    @router.get("")
    async def list_pipelines(
        user: Dict[str, Any] = Depends(_resolve_user),
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List all pipelines for the current user."""
        with get_db() as conn:
            if conversation_id and verify_message_ownership:
                if not _verify_conversation(conn, conversation_id, user["id"]):
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found or access denied")
                query = "SELECT id, name, description, status, message_id, conversation_id, created_at, updated_at FROM pipelines WHERE user_id = ? AND conversation_id = ? ORDER BY updated_at DESC"
                params = (user["id"], conversation_id)
            else:
                query = "SELECT id, name, description, status, message_id, conversation_id, created_at, updated_at FROM pipelines WHERE user_id = ? ORDER BY updated_at DESC"
                params = (user["id"],)

            rows = conn.execute(query, params).fetchall()
            pipelines = []
            for row in rows:
                r = dict(row)
                pipelines.append({
                    "id": r["id"],
                    "name": r.get("name"),
                    "description": r.get("description"),
                    "status": r.get("status", "draft"),
                    "message_id": r.get("message_id"),
                    "conversation_id": r.get("conversation_id"),
                    "created_at": r.get("created_at"),
                    "updated_at": r.get("updated_at"),
                })

        return {"status": "success", "pipelines": pipelines}

    @router.get("/{pipeline_id}")
    async def get_pipeline(
        pipeline_id: str,
        user: Dict[str, Any] = Depends(_resolve_user),
    ) -> Dict[str, Any]:
        """Get a specific pipeline."""
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM pipelines WHERE id = ? AND user_id = ?",
                (pipeline_id, user["id"]),
            ).fetchone()

            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found or access denied")

            r = dict(row)
            pipeline_data = json.loads(r["pipeline_json"])
            pipeline_data["id"] = r["id"]
            pipeline_data["name"] = r["name"]
            pipeline_data["description"] = r["description"]
            pipeline_data["status"] = r["status"]
            pipeline_data["created_at"] = r["created_at"]
            pipeline_data["updated_at"] = r["updated_at"]

        return {"status": "success", "pipeline": pipeline_data}

    @router.put("/{pipeline_id}")
    async def update_pipeline(
        pipeline_id: str,
        pipeline_data: Dict[str, Any],
        user: Dict[str, Any] = Depends(_resolve_user),
    ) -> Dict[str, Any]:
        """Update a pipeline."""
        with get_db() as conn:
            existing = conn.execute(
                "SELECT id FROM pipelines WHERE id = ? AND user_id = ?",
                (pipeline_id, user["id"]),
            ).fetchone()

            if not existing:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found or access denied")

            name = pipeline_data.get("name", "Untitled Pipeline")
            description = pipeline_data.get("description")
            pipeline_json = json.dumps(pipeline_data)
            status_value = pipeline_data.get("status", "draft")
            message_id = pipeline_data.get("message_id")
            conversation_id = pipeline_data.get("conversation_id")

            if verify_message_ownership:
                if message_id:
                    if not _verify_message(conn, message_id, user["id"]):
                        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found or access denied")
                if conversation_id and not _verify_conversation(conn, conversation_id, user["id"]):
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found or access denied")

            updates = ["name = ?", "description = ?", "pipeline_json = ?", "status = ?", "updated_at = ?"]
            params = [name, description, pipeline_json, status_value, datetime.utcnow()]
            if message_id is not None:
                updates.append("message_id = ?")
                params.append(message_id)
            if conversation_id is not None:
                updates.append("conversation_id = ?")
                params.append(conversation_id)
            params.extend([pipeline_id, user["id"]])
            conn.execute(
                f"UPDATE pipelines SET {', '.join(updates)} WHERE id = ? AND user_id = ?",
                params,
            )
            conn.commit()

        return {"status": "success", "message": "Pipeline updated successfully"}

    @router.delete("/{pipeline_id}")
    async def delete_pipeline(
        pipeline_id: str,
        user: Dict[str, Any] = Depends(_resolve_user),
    ) -> Dict[str, Any]:
        """Delete a pipeline."""
        with get_db() as conn:
            result = conn.execute(
                "DELETE FROM pipelines WHERE id = ? AND user_id = ?",
                (pipeline_id, user["id"]),
            )
            conn.commit()
            if result.rowcount == 0:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found or access denied")

        return {"status": "success", "message": "Pipeline deleted successfully"}

    @router.post("/{pipeline_id}/executions")
    async def create_execution(
        pipeline_id: str,
        execution_data: Dict[str, Any],
        user: Dict[str, Any] = Depends(_resolve_user),
    ) -> Dict[str, Any]:
        """Create a pipeline execution record."""
        with get_db() as conn:
            pipeline = conn.execute(
                "SELECT id FROM pipelines WHERE id = ? AND user_id = ?",
                (pipeline_id, user["id"]),
            ).fetchone()

            if not pipeline:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found or access denied")

            execution_id = str(uuid.uuid4())
            execution_log = json.dumps(execution_data.get("execution_log", []))
            status_value = execution_data.get("status", "running")

            conn.execute(
                """INSERT INTO pipeline_executions (id, pipeline_id, user_id, status, started_at, execution_log)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (execution_id, pipeline_id, user["id"], status_value, datetime.utcnow(), execution_log),
            )
            conn.commit()

        return {"status": "success", "execution_id": execution_id}

    @router.get("/{pipeline_id}/executions")
    async def list_executions(
        pipeline_id: str,
        user: Dict[str, Any] = Depends(_resolve_user),
    ) -> Dict[str, Any]:
        """List all executions for a pipeline."""
        with get_db() as conn:
            pipeline = conn.execute(
                "SELECT id FROM pipelines WHERE id = ? AND user_id = ?",
                (pipeline_id, user["id"]),
            ).fetchone()

            if not pipeline:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found or access denied")

            rows = conn.execute(
                "SELECT * FROM pipeline_executions WHERE pipeline_id = ? AND user_id = ? ORDER BY started_at DESC",
                (pipeline_id, user["id"]),
            ).fetchall()

            executions = []
            for row in rows:
                ex = dict(row)
                if ex.get("execution_log"):
                    try:
                        ex["execution_log"] = json.loads(ex["execution_log"])
                    except json.JSONDecodeError:
                        ex["execution_log"] = []
                executions.append(ex)

        return {"status": "success", "executions": executions}

    return router
