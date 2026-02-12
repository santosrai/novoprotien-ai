"""Pipeline persistence API endpoints (normalized schema)."""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import Dict, Any, List, Optional
import json
import uuid
from datetime import datetime

try:
    from ...database.db import get_db
    from ..middleware.auth import get_current_user
except ImportError:
    from database.db import get_db
    from api.middleware.auth import get_current_user

router = APIRouter(prefix="/api/pipelines", tags=["pipelines"])


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _assemble_node(row: Dict[str, Any]) -> Dict[str, Any]:
    """Reconstruct a PipelineNode dict from a pipeline_nodes row."""
    return {
        "id": row["id"],
        "type": row["type"],
        "label": row["label"],
        "config": json.loads(row["config"]) if row.get("config") else {},
        "inputs": json.loads(row["inputs"]) if row.get("inputs") else {},
        "status": row["status"],
        "result_metadata": json.loads(row["result_metadata"]) if row.get("result_metadata") else None,
        "error": row.get("error"),
        "position": {"x": row.get("position_x", 0), "y": row.get("position_y", 0)},
    }


def _assemble_pipeline(pipeline_row, node_rows, edge_rows) -> Dict[str, Any]:
    """Reconstruct a full Pipeline object from normalized table rows."""
    p = dict(pipeline_row)
    return {
        "id": p["id"],
        "name": p.get("name"),
        "description": p.get("description"),
        "status": p.get("status", "draft"),
        "createdAt": p.get("created_at"),
        "updatedAt": p.get("updated_at"),
        "message_id": p.get("message_id"),
        "conversation_id": p.get("conversation_id"),
        "nodes": [_assemble_node(dict(n)) for n in node_rows],
        "edges": [
            {"source": dict(e)["source_node_id"], "target": dict(e)["target_node_id"]}
            for e in edge_rows
        ],
    }


def _strip_pdb_content(data: Any) -> Any:
    """Remove raw PDB content from response data to keep DB lean.
    PDB content stays on disk via user_files."""
    if not data or not isinstance(data, dict):
        return data
    cleaned = {k: v for k, v in data.items() if k != 'pdbContent'}
    return cleaned if cleaned else None


def _sync_node_files(conn, pipeline_id: str, nodes: List[Dict[str, Any]]):
    """Extract and track file references from nodes into pipeline_node_files."""
    # Remove old non-execution file refs for this pipeline (re-sync)
    conn.execute(
        "DELETE FROM pipeline_node_files WHERE pipeline_id = ? AND execution_id IS NULL",
        (pipeline_id,),
    )

    for node in nodes:
        config = node.get("config", {})
        if isinstance(config, str):
            try:
                config = json.loads(config)
            except (json.JSONDecodeError, TypeError):
                config = {}

        node_type = node.get("type", "")
        node_id = node.get("id", "")

        # Input node files
        if node_type == "input_node" and config.get("file_id"):
            file_meta = {}
            for key in ["atoms", "chains", "chain_residue_counts", "total_residues", "suggested_contigs"]:
                if key in config:
                    file_meta[key] = config[key]
            conn.execute("""
                INSERT INTO pipeline_node_files
                    (id, pipeline_id, node_id, role, file_type, filename, file_url, file_id, metadata)
                VALUES (?, ?, ?, 'input', 'pdb', ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()), pipeline_id, node_id,
                config.get("filename"),
                config.get("file_url"),
                config.get("file_id"),
                json.dumps(file_meta) if file_meta else None,
            ))

        # Output file references from result_metadata
        result_meta = node.get("result_metadata")
        if isinstance(result_meta, str):
            try:
                result_meta = json.loads(result_meta)
            except (json.JSONDecodeError, TypeError):
                result_meta = None

        if result_meta and isinstance(result_meta, dict):
            output_file = result_meta.get("output_file")
            if output_file and isinstance(output_file, dict):
                conn.execute("""
                    INSERT INTO pipeline_node_files
                        (id, pipeline_id, node_id, role, file_type, filename, file_url, file_path, file_id)
                    VALUES (?, ?, ?, 'output', 'pdb', ?, ?, ?, ?)
                """, (
                    str(uuid.uuid4()), pipeline_id, node_id,
                    output_file.get("filename"),
                    output_file.get("file_url"),
                    output_file.get("filepath"),
                    output_file.get("file_id"),
                ))


# ---------------------------------------------------------------------------
# Pipeline CRUD
# ---------------------------------------------------------------------------

@router.post("")
async def create_pipeline(
    pipeline_data: Dict[str, Any],
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create or update a pipeline. Decomposes into normalized tables."""
    pipeline_id = pipeline_data.get("id") or str(uuid.uuid4())
    name = pipeline_data.get("name", "Untitled Pipeline")
    description = pipeline_data.get("description")
    status_value = pipeline_data.get("status", "draft")
    message_id = pipeline_data.get("message_id")
    conversation_id = pipeline_data.get("conversation_id")
    now = datetime.utcnow()

    with get_db() as conn:
        # Verify message ownership if provided
        if message_id:
            message = conn.execute(
                "SELECT id, conversation_id, session_id, user_id FROM chat_messages WHERE id = ? AND user_id = ?",
                (message_id, user["id"]),
            ).fetchone()
            if not message:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found or access denied")
            if not conversation_id:
                msg = dict(message)
                conversation_id = msg.get("conversation_id") or msg.get("session_id")

        if conversation_id:
            conversation = conn.execute(
                "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
                (conversation_id, user["id"]),
            ).fetchone()
            if not conversation:
                conversation = conn.execute(
                    "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?",
                    (conversation_id, user["id"]),
                ).fetchone()
            if not conversation:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found or access denied")

        # 1. Upsert pipeline metadata
        existing = conn.execute(
            "SELECT id FROM pipelines WHERE id = ? AND user_id = ?",
            (pipeline_id, user["id"]),
        ).fetchone()

        if existing:
            updates = ["name = ?", "description = ?", "status = ?", "updated_at = ?"]
            params: list = [name, description, status_value, now]
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
            conn.execute("""
                INSERT INTO pipelines (id, user_id, message_id, conversation_id, name, description, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (pipeline_id, user["id"], message_id, conversation_id, name, description, status_value, now, now))

        # 2. Sync nodes - delete removed nodes, upsert existing
        incoming_nodes = pipeline_data.get("nodes", [])
        incoming_node_ids = [n.get("id") for n in incoming_nodes if n.get("id")]

        if incoming_node_ids:
            placeholders = ",".join("?" * len(incoming_node_ids))
            conn.execute(
                f"DELETE FROM pipeline_nodes WHERE pipeline_id = ? AND id NOT IN ({placeholders})",
                [pipeline_id] + incoming_node_ids,
            )
        else:
            conn.execute("DELETE FROM pipeline_nodes WHERE pipeline_id = ?", (pipeline_id,))

        for node in incoming_nodes:
            node_id = node.get("id")
            if not node_id:
                continue
            position = node.get("position", {})
            config_val = node.get("config", {})
            inputs_val = node.get("inputs", {})
            result_meta = node.get("result_metadata")

            config_json = json.dumps(config_val) if isinstance(config_val, dict) else (config_val or "{}")
            inputs_json = json.dumps(inputs_val) if isinstance(inputs_val, dict) else (inputs_val or "{}")
            result_json = json.dumps(result_meta) if result_meta else None

            # Use INSERT OR REPLACE for upsert on composite PK
            conn.execute("""
                INSERT OR REPLACE INTO pipeline_nodes
                    (id, pipeline_id, type, label, config, inputs, status,
                     result_metadata, error, position_x, position_y, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(
                    (SELECT created_at FROM pipeline_nodes WHERE id = ? AND pipeline_id = ?),
                    ?
                ), ?)
            """, (
                node_id, pipeline_id,
                node.get("type", "input_node"),
                node.get("label", ""),
                config_json, inputs_json,
                node.get("status", "idle"),
                result_json,
                node.get("error"),
                position.get("x", 0), position.get("y", 0),
                node_id, pipeline_id, now,  # For COALESCE
                now,
            ))

        # 3. Replace edges
        conn.execute("DELETE FROM pipeline_edges WHERE pipeline_id = ?", (pipeline_id,))
        for edge in pipeline_data.get("edges", []):
            source = edge.get("source", "")
            target = edge.get("target", "")
            if source and target:
                conn.execute("""
                    INSERT OR IGNORE INTO pipeline_edges (id, pipeline_id, source_node_id, target_node_id)
                    VALUES (?, ?, ?, ?)
                """, (str(uuid.uuid4()), pipeline_id, source, target))

        # 4. Sync file references
        _sync_node_files(conn, pipeline_id, incoming_nodes)

    return {
        "status": "success",
        "pipeline_id": pipeline_id,
        "message": "Pipeline saved successfully",
    }


@router.get("")
async def list_pipelines(
    user: Dict[str, Any] = Depends(get_current_user),
    conversation_id: Optional[str] = None,
    full: bool = False,
) -> Dict[str, Any]:
    """List all pipelines for the current user. When full=true, includes nodes and edges."""
    with get_db() as conn:
        if conversation_id:
            conversation = conn.execute(
                "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
                (conversation_id, user["id"]),
            ).fetchone()
            if not conversation:
                conversation = conn.execute(
                    "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?",
                    (conversation_id, user["id"]),
                ).fetchone()
            if not conversation:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found or access denied")

            pipeline_rows = conn.execute(
                "SELECT * FROM pipelines WHERE user_id = ? AND conversation_id = ? ORDER BY updated_at DESC",
                (user["id"], conversation_id),
            ).fetchall()
        else:
            pipeline_rows = conn.execute(
                "SELECT * FROM pipelines WHERE user_id = ? ORDER BY updated_at DESC",
                (user["id"],),
            ).fetchall()

        pipelines = []
        for p_row in pipeline_rows:
            p = dict(p_row)
            if full:
                nodes = conn.execute(
                    "SELECT * FROM pipeline_nodes WHERE pipeline_id = ? ORDER BY created_at",
                    (p["id"],),
                ).fetchall()
                edges = conn.execute(
                    "SELECT * FROM pipeline_edges WHERE pipeline_id = ?",
                    (p["id"],),
                ).fetchall()
                pipelines.append(_assemble_pipeline(p_row, nodes, edges))
            else:
                pipelines.append({
                    "id": p["id"],
                    "name": p.get("name"),
                    "description": p.get("description"),
                    "status": p.get("status", "draft"),
                    "message_id": p.get("message_id"),
                    "conversation_id": p.get("conversation_id"),
                    "created_at": p.get("created_at"),
                    "updated_at": p.get("updated_at"),
                })

        return {"status": "success", "pipelines": pipelines}


@router.get("/{pipeline_id}")
async def get_pipeline(
    pipeline_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get a specific pipeline with all nodes and edges."""
    with get_db() as conn:
        pipeline = conn.execute(
            "SELECT * FROM pipelines WHERE id = ? AND user_id = ?",
            (pipeline_id, user["id"]),
        ).fetchone()
        if not pipeline:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found or access denied")

        nodes = conn.execute(
            "SELECT * FROM pipeline_nodes WHERE pipeline_id = ? ORDER BY created_at",
            (pipeline_id,),
        ).fetchall()
        edges = conn.execute(
            "SELECT * FROM pipeline_edges WHERE pipeline_id = ?",
            (pipeline_id,),
        ).fetchall()

        return {
            "status": "success",
            "pipeline": _assemble_pipeline(pipeline, nodes, edges),
        }


@router.put("/{pipeline_id}")
async def update_pipeline(
    pipeline_id: str,
    pipeline_data: Dict[str, Any],
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Update a pipeline. Delegates to create_pipeline (upsert logic)."""
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM pipelines WHERE id = ? AND user_id = ?",
            (pipeline_id, user["id"]),
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found or access denied")

    pipeline_data["id"] = pipeline_id
    return await create_pipeline(pipeline_data, user)


@router.delete("/{pipeline_id}")
async def delete_pipeline(
    pipeline_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Delete a pipeline. Cascade deletes nodes, edges, executions, and file refs."""
    with get_db() as conn:
        result = conn.execute(
            "DELETE FROM pipelines WHERE id = ? AND user_id = ?",
            (pipeline_id, user["id"]),
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found or access denied")

    return {"status": "success", "message": "Pipeline deleted successfully"}


# ---------------------------------------------------------------------------
# Execution endpoints
# ---------------------------------------------------------------------------

@router.post("/{pipeline_id}/executions")
async def create_execution(
    pipeline_id: str,
    execution_data: Dict[str, Any],
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create an execution record with per-node execution entries."""
    with get_db() as conn:
        pipeline = conn.execute(
            "SELECT id FROM pipelines WHERE id = ? AND user_id = ?",
            (pipeline_id, user["id"]),
        ).fetchone()
        if not pipeline:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found or access denied")

        execution_id = str(uuid.uuid4())
        status_value = execution_data.get("status", "running")
        trigger_type = execution_data.get("trigger_type", "manual")
        now = datetime.utcnow()

        conn.execute("""
            INSERT INTO pipeline_executions (id, pipeline_id, user_id, status, trigger_type, started_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (execution_id, pipeline_id, user["id"], status_value, trigger_type, now))

        # Insert per-node execution entries
        for order, log in enumerate(execution_data.get("execution_log", [])):
            ne_id = str(uuid.uuid4())
            req = log.get("request", {}) or {}
            resp = log.get("response", {}) or {}

            # Strip raw PDB content from response data
            resp_data = _strip_pdb_content(resp.get("data"))

            conn.execute("""
                INSERT INTO pipeline_node_executions
                    (id, execution_id, node_id, pipeline_id, node_label, node_type,
                     status, execution_order, started_at, completed_at, duration_ms,
                     error, input_data, output_data,
                     request_method, request_url, request_headers, request_body,
                     response_status, response_status_text, response_headers, response_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ne_id, execution_id, log.get("nodeId", ""), pipeline_id,
                log.get("nodeLabel", ""), log.get("nodeType", ""),
                log.get("status", "pending"), order,
                log.get("startedAt"), log.get("completedAt"),
                log.get("duration"),
                log.get("error"),
                json.dumps(log.get("input")) if log.get("input") else None,
                json.dumps(log.get("output")) if log.get("output") else None,
                req.get("method"), req.get("url"),
                json.dumps(req.get("headers")) if req.get("headers") else None,
                json.dumps(req.get("body")) if req.get("body") else None,
                resp.get("status"), resp.get("statusText"),
                json.dumps(resp.get("headers")) if resp.get("headers") else None,
                json.dumps(resp_data) if resp_data else None,
            ))

            # Track output files
            output = log.get("output", {})
            if output and isinstance(output, dict):
                output_file = output.get("output_file") or output.get("file_info")
                if output_file and isinstance(output_file, dict):
                    conn.execute("""
                        INSERT INTO pipeline_node_files
                            (id, pipeline_id, node_id, execution_id, node_execution_id,
                             role, file_type, filename, file_url, file_path, file_id)
                        VALUES (?, ?, ?, ?, ?, 'output', 'pdb', ?, ?, ?, ?)
                    """, (
                        str(uuid.uuid4()), pipeline_id, log.get("nodeId", ""),
                        execution_id, ne_id,
                        output_file.get("filename"),
                        output_file.get("file_url"),
                        output_file.get("filepath"),
                        output_file.get("file_id"),
                    ))

    return {"status": "success", "execution_id": execution_id}


@router.get("/{pipeline_id}/executions")
async def list_executions(
    pipeline_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """List executions for a pipeline. Reconstructs execution_log array for frontend compatibility."""
    with get_db() as conn:
        pipeline = conn.execute(
            "SELECT id FROM pipelines WHERE id = ? AND user_id = ?",
            (pipeline_id, user["id"]),
        ).fetchone()
        if not pipeline:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found or access denied")

        exec_rows = conn.execute("""
            SELECT * FROM pipeline_executions
            WHERE pipeline_id = ? AND user_id = ?
            ORDER BY started_at DESC
        """, (pipeline_id, user["id"])).fetchall()

        executions = []
        for ex_row in exec_rows:
            ex = dict(ex_row)

            node_exec_rows = conn.execute("""
                SELECT * FROM pipeline_node_executions
                WHERE execution_id = ?
                ORDER BY execution_order
            """, (ex["id"],)).fetchall()

            # Reconstruct execution_log array for frontend compatibility
            execution_log = []
            for ne_row in node_exec_rows:
                ne = dict(ne_row)
                entry: Dict[str, Any] = {
                    "nodeId": ne["node_id"],
                    "nodeLabel": ne["node_label"],
                    "nodeType": ne["node_type"],
                    "status": ne["status"],
                    "startedAt": ne.get("started_at"),
                    "completedAt": ne.get("completed_at"),
                    "duration": ne.get("duration_ms"),
                    "error": ne.get("error"),
                }
                if ne.get("input_data"):
                    try:
                        entry["input"] = json.loads(ne["input_data"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                if ne.get("output_data"):
                    try:
                        entry["output"] = json.loads(ne["output_data"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                if ne.get("request_method"):
                    entry["request"] = {
                        "method": ne["request_method"],
                        "url": ne.get("request_url"),
                    }
                    if ne.get("request_headers"):
                        try:
                            entry["request"]["headers"] = json.loads(ne["request_headers"])
                        except (json.JSONDecodeError, TypeError):
                            pass
                    if ne.get("request_body"):
                        try:
                            entry["request"]["body"] = json.loads(ne["request_body"])
                        except (json.JSONDecodeError, TypeError):
                            pass
                if ne.get("response_status") is not None:
                    entry["response"] = {
                        "status": ne["response_status"],
                        "statusText": ne.get("response_status_text"),
                    }
                    if ne.get("response_headers"):
                        try:
                            entry["response"]["headers"] = json.loads(ne["response_headers"])
                        except (json.JSONDecodeError, TypeError):
                            pass
                    if ne.get("response_data"):
                        try:
                            entry["response"]["data"] = json.loads(ne["response_data"])
                        except (json.JSONDecodeError, TypeError):
                            pass

                execution_log.append(entry)

            ex["execution_log"] = execution_log
            executions.append(ex)

        return {"status": "success", "executions": executions}


# ---------------------------------------------------------------------------
# Granular node endpoints
# ---------------------------------------------------------------------------

@router.patch("/{pipeline_id}/nodes/{node_id}")
async def update_node(
    pipeline_id: str,
    node_id: str,
    node_data: Dict[str, Any],
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Update a single node's config, status, or result_metadata."""
    with get_db() as conn:
        # Verify pipeline ownership
        pipeline = conn.execute(
            "SELECT id FROM pipelines WHERE id = ? AND user_id = ?",
            (pipeline_id, user["id"]),
        ).fetchone()
        if not pipeline:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found or access denied")

        # Verify node exists
        node = conn.execute(
            "SELECT id FROM pipeline_nodes WHERE id = ? AND pipeline_id = ?",
            (node_id, pipeline_id),
        ).fetchone()
        if not node:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")

        # Build dynamic update
        updates = []
        params: list = []

        if "config" in node_data:
            config_val = node_data["config"]
            updates.append("config = ?")
            params.append(json.dumps(config_val) if isinstance(config_val, dict) else config_val)

        if "inputs" in node_data:
            inputs_val = node_data["inputs"]
            updates.append("inputs = ?")
            params.append(json.dumps(inputs_val) if isinstance(inputs_val, dict) else inputs_val)

        if "status" in node_data:
            updates.append("status = ?")
            params.append(node_data["status"])

        if "result_metadata" in node_data:
            rm = node_data["result_metadata"]
            updates.append("result_metadata = ?")
            params.append(json.dumps(rm) if rm else None)

        if "error" in node_data:
            updates.append("error = ?")
            params.append(node_data["error"])

        if "label" in node_data:
            updates.append("label = ?")
            params.append(node_data["label"])

        if "position" in node_data:
            pos = node_data["position"]
            updates.append("position_x = ?")
            params.append(pos.get("x", 0))
            updates.append("position_y = ?")
            params.append(pos.get("y", 0))

        if not updates:
            return {"status": "success", "message": "No updates provided"}

        updates.append("updated_at = ?")
        params.append(datetime.utcnow())
        params.extend([node_id, pipeline_id])

        conn.execute(
            f"UPDATE pipeline_nodes SET {', '.join(updates)} WHERE id = ? AND pipeline_id = ?",
            params,
        )

        # Also update pipeline updated_at
        conn.execute(
            "UPDATE pipelines SET updated_at = ? WHERE id = ?",
            (datetime.utcnow(), pipeline_id),
        )

    return {"status": "success", "message": "Node updated successfully"}


@router.get("/{pipeline_id}/nodes/{node_id}/files")
async def get_node_files(
    pipeline_id: str,
    node_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """List all files associated with a specific node."""
    with get_db() as conn:
        pipeline = conn.execute(
            "SELECT id FROM pipelines WHERE id = ? AND user_id = ?",
            (pipeline_id, user["id"]),
        ).fetchone()
        if not pipeline:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found or access denied")

        rows = conn.execute("""
            SELECT * FROM pipeline_node_files
            WHERE pipeline_id = ? AND node_id = ?
            ORDER BY created_at
        """, (pipeline_id, node_id)).fetchall()

        files = []
        for row in rows:
            f = dict(row)
            if f.get("metadata"):
                try:
                    f["metadata"] = json.loads(f["metadata"])
                except (json.JSONDecodeError, TypeError):
                    pass
            files.append(f)

        return {"status": "success", "files": files}


@router.get("/{pipeline_id}/files")
async def get_pipeline_files(
    pipeline_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """List all files across all nodes in a pipeline."""
    with get_db() as conn:
        pipeline = conn.execute(
            "SELECT id FROM pipelines WHERE id = ? AND user_id = ?",
            (pipeline_id, user["id"]),
        ).fetchone()
        if not pipeline:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found or access denied")

        rows = conn.execute("""
            SELECT * FROM pipeline_node_files
            WHERE pipeline_id = ?
            ORDER BY node_id, created_at
        """, (pipeline_id,)).fetchall()

        files = []
        for row in rows:
            f = dict(row)
            if f.get("metadata"):
                try:
                    f["metadata"] = json.loads(f["metadata"])
                except (json.JSONDecodeError, TypeError):
                    pass
            files.append(f)

        return {"status": "success", "files": files}


@router.post("/{pipeline_id}/executions/{execution_id}/nodes/{node_id}")
async def upsert_node_execution(
    pipeline_id: str,
    execution_id: str,
    node_id: str,
    node_exec_data: Dict[str, Any],
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create or update a single node execution within an execution session."""
    with get_db() as conn:
        pipeline = conn.execute(
            "SELECT id FROM pipelines WHERE id = ? AND user_id = ?",
            (pipeline_id, user["id"]),
        ).fetchone()
        if not pipeline:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found or access denied")

        execution = conn.execute(
            "SELECT id FROM pipeline_executions WHERE id = ? AND pipeline_id = ?",
            (execution_id, pipeline_id),
        ).fetchone()
        if not execution:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")

        req = node_exec_data.get("request", {}) or {}
        resp = node_exec_data.get("response", {}) or {}
        resp_data = _strip_pdb_content(resp.get("data"))

        # Check if node execution already exists
        existing = conn.execute(
            "SELECT id FROM pipeline_node_executions WHERE execution_id = ? AND node_id = ? AND pipeline_id = ?",
            (execution_id, node_id, pipeline_id),
        ).fetchone()

        if existing:
            ne_id = dict(existing)["id"]
            conn.execute("""
                UPDATE pipeline_node_executions SET
                    status = ?, completed_at = ?, duration_ms = ?, error = ?,
                    input_data = ?, output_data = ?,
                    request_method = ?, request_url = ?, request_headers = ?, request_body = ?,
                    response_status = ?, response_status_text = ?, response_headers = ?, response_data = ?
                WHERE id = ?
            """, (
                node_exec_data.get("status", "pending"),
                node_exec_data.get("completedAt"),
                node_exec_data.get("duration"),
                node_exec_data.get("error"),
                json.dumps(node_exec_data.get("input")) if node_exec_data.get("input") else None,
                json.dumps(node_exec_data.get("output")) if node_exec_data.get("output") else None,
                req.get("method"), req.get("url"),
                json.dumps(req.get("headers")) if req.get("headers") else None,
                json.dumps(req.get("body")) if req.get("body") else None,
                resp.get("status"), resp.get("statusText"),
                json.dumps(resp.get("headers")) if resp.get("headers") else None,
                json.dumps(resp_data) if resp_data else None,
                ne_id,
            ))
        else:
            ne_id = str(uuid.uuid4())
            conn.execute("""
                INSERT INTO pipeline_node_executions
                    (id, execution_id, node_id, pipeline_id, node_label, node_type,
                     status, execution_order, started_at, completed_at, duration_ms,
                     error, input_data, output_data,
                     request_method, request_url, request_headers, request_body,
                     response_status, response_status_text, response_headers, response_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ne_id, execution_id, node_id, pipeline_id,
                node_exec_data.get("nodeLabel", ""),
                node_exec_data.get("nodeType", ""),
                node_exec_data.get("status", "pending"),
                node_exec_data.get("executionOrder"),
                node_exec_data.get("startedAt"),
                node_exec_data.get("completedAt"),
                node_exec_data.get("duration"),
                node_exec_data.get("error"),
                json.dumps(node_exec_data.get("input")) if node_exec_data.get("input") else None,
                json.dumps(node_exec_data.get("output")) if node_exec_data.get("output") else None,
                req.get("method"), req.get("url"),
                json.dumps(req.get("headers")) if req.get("headers") else None,
                json.dumps(req.get("body")) if req.get("body") else None,
                resp.get("status"), resp.get("statusText"),
                json.dumps(resp.get("headers")) if resp.get("headers") else None,
                json.dumps(resp_data) if resp_data else None,
            ))

    return {"status": "success", "node_execution_id": ne_id}
