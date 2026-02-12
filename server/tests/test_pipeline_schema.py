"""Comprehensive tests for the normalized pipeline database schema.

Covers:
1. Pipeline CRUD
2. Node CRUD
3. Edge CRUD
4. Execution Flow
5. HTTP Request/Response Tracking
6. File Tracking
7. Typed Views
8. Data Integrity / Cascades
9. Edge Cases
"""

import sqlite3
import json
import uuid
import pytest
from datetime import datetime, timedelta, timezone
from .conftest import make_pipeline_id, make_node_id


# -----------------------------------------------------------------------
# 1. Pipeline CRUD
# -----------------------------------------------------------------------

class TestPipelineCRUD:
    """Pipeline create, read, update, delete operations."""

    def test_create_empty_pipeline(self, db, seed_user):
        pid = make_pipeline_id()
        db.execute(
            "INSERT INTO pipelines (id, user_id, name, status) VALUES (?, ?, ?, ?)",
            (pid, seed_user, "Empty", "draft"),
        )
        db.commit()

        row = db.execute("SELECT * FROM pipelines WHERE id = ?", (pid,)).fetchone()
        assert row is not None
        assert dict(row)["name"] == "Empty"
        assert dict(row)["status"] == "draft"

    def test_create_single_node_pipeline(self, insert_pipeline):
        nodes = [{"id": "n1", "type": "input_node", "label": "PDB Input"}]
        pid = insert_pipeline(name="Single Node", nodes=nodes)

        assert pid is not None

    def test_create_full_pipeline(self, db, insert_pipeline):
        nodes = [
            {"id": "n1", "type": "input_node", "label": "PDB Input", "config": {"filename": "test.pdb"}},
            {"id": "n2", "type": "rfdiffusion_node", "label": "RFdiffusion", "config": {"contigs": "50-100"}},
            {"id": "n3", "type": "proteinmpnn_node", "label": "ProteinMPNN", "config": {"num_sequences": 4}},
            {"id": "n4", "type": "alphafold_node", "label": "AlphaFold", "config": {"recycle_count": 3}},
        ]
        edges = [
            {"source": "n1", "target": "n2"},
            {"source": "n2", "target": "n3"},
            {"source": "n3", "target": "n4"},
        ]
        pid = insert_pipeline(name="Full Pipeline", nodes=nodes, edges=edges)

        node_rows = db.execute(
            "SELECT * FROM pipeline_nodes WHERE pipeline_id = ? ORDER BY created_at", (pid,)
        ).fetchall()
        edge_rows = db.execute(
            "SELECT * FROM pipeline_edges WHERE pipeline_id = ?", (pid,)
        ).fetchall()

        assert len(node_rows) == 4
        assert len(edge_rows) == 3

    def test_update_pipeline_metadata(self, db, insert_pipeline):
        pid = insert_pipeline(name="Original Name")
        db.execute("UPDATE pipelines SET name = ?, description = ? WHERE id = ?",
                    ("Updated Name", "A description", pid))
        db.commit()

        row = db.execute("SELECT * FROM pipelines WHERE id = ?", (pid,)).fetchone()
        assert dict(row)["name"] == "Updated Name"
        assert dict(row)["description"] == "A description"

    def test_delete_pipeline(self, db, insert_pipeline):
        nodes = [{"id": "n1", "type": "input_node", "label": "X"}]
        pid = insert_pipeline(nodes=nodes)

        db.execute("DELETE FROM pipelines WHERE id = ?", (pid,))
        db.commit()

        assert db.execute("SELECT id FROM pipelines WHERE id = ?", (pid,)).fetchone() is None

    def test_delete_pipeline_cascades_nodes_and_edges(self, db, insert_pipeline):
        nodes = [
            {"id": "n1", "type": "input_node", "label": "A"},
            {"id": "n2", "type": "rfdiffusion_node", "label": "B"},
        ]
        edges = [{"source": "n1", "target": "n2"}]
        pid = insert_pipeline(nodes=nodes, edges=edges)

        db.execute("DELETE FROM pipelines WHERE id = ?", (pid,))
        db.commit()

        assert db.execute("SELECT * FROM pipeline_nodes WHERE pipeline_id = ?", (pid,)).fetchone() is None
        assert db.execute("SELECT * FROM pipeline_edges WHERE pipeline_id = ?", (pid,)).fetchone() is None

    def test_access_control_user_isolation(self, db, insert_pipeline, other_user):
        pid = insert_pipeline(name="User A pipeline")

        # User B should not see User A's pipeline via user_id filter
        row = db.execute(
            "SELECT * FROM pipelines WHERE id = ? AND user_id = ?",
            (pid, other_user),
        ).fetchone()
        assert row is None

    def test_status_check_constraint(self, db, seed_user):
        pid = make_pipeline_id()
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO pipelines (id, user_id, name, status) VALUES (?, ?, ?, ?)",
                (pid, seed_user, "Bad Status", "invalid_status"),
            )


# -----------------------------------------------------------------------
# 2. Node CRUD
# -----------------------------------------------------------------------

class TestNodeCRUD:
    """Individual node create, read, update, delete operations."""

    @pytest.mark.parametrize("node_type,config", [
        ("input_node", {"filename": "test.pdb", "file_id": "f1", "atoms": 500}),
        ("rfdiffusion_node", {"contigs": "50-100", "num_designs": 2, "design_mode": "unconditional"}),
        ("proteinmpnn_node", {"num_sequences": 8, "temperature": 0.1}),
        ("alphafold_node", {"recycle_count": 3, "num_relax": 1}),
        ("openfold2_node", {"sequence": "MVLSEGE", "relax_prediction": True}),
        ("message_input_node", {"message": "hello"}),
        ("http_request_node", {"url": "https://api.example.com", "method": "POST"}),
    ])
    def test_create_all_node_types(self, db, insert_pipeline, node_type, config):
        nid = make_node_id()
        nodes = [{"id": nid, "type": node_type, "label": node_type, "config": config}]
        pid = insert_pipeline(nodes=nodes)

        row = db.execute(
            "SELECT * FROM pipeline_nodes WHERE id = ? AND pipeline_id = ?", (nid, pid)
        ).fetchone()
        assert row is not None
        stored_config = json.loads(dict(row)["config"])
        assert stored_config == config

    def test_update_node_config_roundtrip(self, db, insert_pipeline):
        nid = "upd_node"
        nodes = [{"id": nid, "type": "rfdiffusion_node", "label": "RF", "config": {"contigs": "50-100"}}]
        pid = insert_pipeline(nodes=nodes)

        new_config = {"contigs": "100-200", "num_designs": 5, "hotspot_res": ["A50", "A51"]}
        db.execute(
            "UPDATE pipeline_nodes SET config = ? WHERE id = ? AND pipeline_id = ?",
            (json.dumps(new_config), nid, pid),
        )
        db.commit()

        row = db.execute(
            "SELECT config FROM pipeline_nodes WHERE id = ? AND pipeline_id = ?", (nid, pid)
        ).fetchone()
        assert json.loads(dict(row)["config"]) == new_config

    def test_update_node_status_transitions(self, db, insert_pipeline):
        nid = "status_node"
        nodes = [{"id": nid, "type": "input_node", "label": "Input", "status": "idle"}]
        pid = insert_pipeline(nodes=nodes)

        for new_status in ["pending", "running", "success", "completed"]:
            db.execute(
                "UPDATE pipeline_nodes SET status = ? WHERE id = ? AND pipeline_id = ?",
                (new_status, nid, pid),
            )
            db.commit()
            row = db.execute(
                "SELECT status FROM pipeline_nodes WHERE id = ? AND pipeline_id = ?", (nid, pid)
            ).fetchone()
            assert dict(row)["status"] == new_status

    def test_store_retrieve_result_metadata(self, db, insert_pipeline):
        nid = "meta_node"
        meta = {
            "output_file": {"filename": "design_1.pdb", "file_id": "f123"},
            "scores": {"plddt": 85.2, "ptm": 0.91},
            "nested": {"level1": {"level2": {"value": 42}}},
        }
        nodes = [{"id": nid, "type": "rfdiffusion_node", "label": "RF", "result_metadata": meta}]
        pid = insert_pipeline(nodes=nodes)

        row = db.execute(
            "SELECT result_metadata FROM pipeline_nodes WHERE id = ? AND pipeline_id = ?", (nid, pid)
        ).fetchone()
        assert json.loads(dict(row)["result_metadata"]) == meta

    def test_delete_node_cascades_edges(self, db, insert_pipeline):
        nodes = [
            {"id": "a", "type": "input_node", "label": "A"},
            {"id": "b", "type": "rfdiffusion_node", "label": "B"},
            {"id": "c", "type": "proteinmpnn_node", "label": "C"},
        ]
        edges = [{"source": "a", "target": "b"}, {"source": "b", "target": "c"}]
        pid = insert_pipeline(nodes=nodes, edges=edges)

        # Delete node b should cascade edges a->b and b->c
        db.execute("DELETE FROM pipeline_nodes WHERE id = ? AND pipeline_id = ?", ("b", pid))
        db.commit()

        remaining_edges = db.execute(
            "SELECT * FROM pipeline_edges WHERE pipeline_id = ?", (pid,)
        ).fetchall()
        assert len(remaining_edges) == 0

    def test_invalid_node_type_rejected(self, db, insert_pipeline):
        pid = insert_pipeline()  # Empty pipeline
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                """INSERT INTO pipeline_nodes (id, pipeline_id, type, label, config, inputs)
                   VALUES (?, ?, ?, ?, '{}', '{}')""",
                ("bad", pid, "invalid_type", "Bad Node"),
            )

    def test_position_persistence(self, db, insert_pipeline):
        nid = "pos_node"
        nodes = [{"id": nid, "type": "input_node", "label": "Pos", "position_x": 150.5, "position_y": 300.0}]
        pid = insert_pipeline(nodes=nodes)

        row = db.execute(
            "SELECT position_x, position_y FROM pipeline_nodes WHERE id = ? AND pipeline_id = ?",
            (nid, pid),
        ).fetchone()
        d = dict(row)
        assert d["position_x"] == 150.5
        assert d["position_y"] == 300.0

    def test_composite_primary_key(self, db, insert_pipeline):
        """Same node ID in different pipelines should be allowed."""
        nid = "shared_id"
        pid1 = insert_pipeline(name="P1", nodes=[{"id": nid, "type": "input_node", "label": "A"}])
        pid2 = insert_pipeline(name="P2", nodes=[{"id": nid, "type": "input_node", "label": "B"}])

        count = db.execute(
            "SELECT COUNT(*) as cnt FROM pipeline_nodes WHERE id = ?", (nid,)
        ).fetchone()
        assert dict(count)["cnt"] == 2


# -----------------------------------------------------------------------
# 3. Edge CRUD
# -----------------------------------------------------------------------

class TestEdgeCRUD:
    """Edge create, read, constraint tests."""

    def test_create_valid_edge(self, db, insert_pipeline):
        nodes = [
            {"id": "a", "type": "input_node", "label": "A"},
            {"id": "b", "type": "rfdiffusion_node", "label": "B"},
        ]
        edges = [{"source": "a", "target": "b"}]
        pid = insert_pipeline(nodes=nodes, edges=edges)

        rows = db.execute("SELECT * FROM pipeline_edges WHERE pipeline_id = ?", (pid,)).fetchall()
        assert len(rows) == 1
        e = dict(rows[0])
        assert e["source_node_id"] == "a"
        assert e["target_node_id"] == "b"

    def test_duplicate_edge_rejected(self, db, insert_pipeline):
        nodes = [
            {"id": "a", "type": "input_node", "label": "A"},
            {"id": "b", "type": "rfdiffusion_node", "label": "B"},
        ]
        edges = [{"source": "a", "target": "b"}]
        pid = insert_pipeline(nodes=nodes, edges=edges)

        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO pipeline_edges (id, pipeline_id, source_node_id, target_node_id) VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), pid, "a", "b"),
            )

    def test_edge_to_nonexistent_node_rejected(self, db, insert_pipeline):
        nodes = [{"id": "a", "type": "input_node", "label": "A"}]
        pid = insert_pipeline(nodes=nodes)

        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO pipeline_edges (id, pipeline_id, source_node_id, target_node_id) VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), pid, "a", "nonexistent"),
            )

    def test_linear_chain(self, db, insert_pipeline):
        nodes = [
            {"id": "a", "type": "input_node", "label": "A"},
            {"id": "b", "type": "rfdiffusion_node", "label": "B"},
            {"id": "c", "type": "proteinmpnn_node", "label": "C"},
            {"id": "d", "type": "alphafold_node", "label": "D"},
        ]
        edges = [
            {"source": "a", "target": "b"},
            {"source": "b", "target": "c"},
            {"source": "c", "target": "d"},
        ]
        pid = insert_pipeline(nodes=nodes, edges=edges)

        count = db.execute(
            "SELECT COUNT(*) as cnt FROM pipeline_edges WHERE pipeline_id = ?", (pid,)
        ).fetchone()
        assert dict(count)["cnt"] == 3

    def test_diamond_pattern(self, db, insert_pipeline):
        nodes = [
            {"id": "a", "type": "input_node", "label": "A"},
            {"id": "b", "type": "rfdiffusion_node", "label": "B"},
            {"id": "c", "type": "proteinmpnn_node", "label": "C"},
            {"id": "d", "type": "alphafold_node", "label": "D"},
        ]
        edges = [
            {"source": "a", "target": "b"},
            {"source": "a", "target": "c"},
            {"source": "b", "target": "d"},
            {"source": "c", "target": "d"},
        ]
        pid = insert_pipeline(nodes=nodes, edges=edges)

        count = db.execute(
            "SELECT COUNT(*) as cnt FROM pipeline_edges WHERE pipeline_id = ?", (pid,)
        ).fetchone()
        assert dict(count)["cnt"] == 4


# -----------------------------------------------------------------------
# 4. Execution Flow
# -----------------------------------------------------------------------

class TestExecutionFlow:
    """Pipeline execution recording and retrieval."""

    def test_full_pipeline_execution(self, db, insert_pipeline, insert_execution):
        nodes = [
            {"id": "n1", "type": "input_node", "label": "Input"},
            {"id": "n2", "type": "rfdiffusion_node", "label": "RF"},
        ]
        pid = insert_pipeline(nodes=nodes, edges=[{"source": "n1", "target": "n2"}])

        logs = [
            {"node_id": "n1", "node_label": "Input", "node_type": "input_node", "status": "success",
             "started_at": datetime.now(timezone.utc).isoformat(), "duration_ms": 50},
            {"node_id": "n2", "node_label": "RF", "node_type": "rfdiffusion_node", "status": "success",
             "started_at": datetime.now(timezone.utc).isoformat(), "duration_ms": 5000},
        ]
        eid, ne_ids = insert_execution(pid, node_logs=logs)

        rows = db.execute(
            "SELECT * FROM pipeline_node_executions WHERE execution_id = ? ORDER BY execution_order",
            (eid,),
        ).fetchall()
        assert len(rows) == 2
        assert dict(rows[0])["node_id"] == "n1"
        assert dict(rows[1])["node_id"] == "n2"

    def test_execution_order_preserved(self, db, insert_pipeline, insert_execution):
        nodes = [
            {"id": "n1", "type": "input_node", "label": "Input"},
            {"id": "n2", "type": "rfdiffusion_node", "label": "RF"},
            {"id": "n3", "type": "proteinmpnn_node", "label": "MPNN"},
        ]
        pid = insert_pipeline(nodes=nodes)

        logs = [
            {"node_id": "n1", "node_label": "Input", "node_type": "input_node", "status": "success"},
            {"node_id": "n2", "node_label": "RF", "node_type": "rfdiffusion_node", "status": "success"},
            {"node_id": "n3", "node_label": "MPNN", "node_type": "proteinmpnn_node", "status": "success"},
        ]
        eid, _ = insert_execution(pid, node_logs=logs)

        rows = db.execute(
            "SELECT execution_order, node_id FROM pipeline_node_executions WHERE execution_id = ? ORDER BY execution_order",
            (eid,),
        ).fetchall()
        orders = [dict(r)["execution_order"] for r in rows]
        assert orders == [0, 1, 2]

    def test_node_failure_mid_pipeline(self, db, insert_pipeline, insert_execution):
        nodes = [
            {"id": "n1", "type": "input_node", "label": "Input"},
            {"id": "n2", "type": "rfdiffusion_node", "label": "RF"},
            {"id": "n3", "type": "proteinmpnn_node", "label": "MPNN"},
        ]
        pid = insert_pipeline(nodes=nodes)

        logs = [
            {"node_id": "n1", "node_label": "Input", "node_type": "input_node", "status": "success"},
            {"node_id": "n2", "node_label": "RF", "node_type": "rfdiffusion_node", "status": "error",
             "error": "API timeout"},
            {"node_id": "n3", "node_label": "MPNN", "node_type": "proteinmpnn_node", "status": "pending"},
        ]
        eid, _ = insert_execution(pid, node_logs=logs, status="failed")

        # Check execution status
        exec_row = db.execute("SELECT status FROM pipeline_executions WHERE id = ?", (eid,)).fetchone()
        assert dict(exec_row)["status"] == "failed"

        # Check individual node statuses
        ne_rows = db.execute(
            "SELECT node_id, status, error FROM pipeline_node_executions WHERE execution_id = ? ORDER BY execution_order",
            (eid,),
        ).fetchall()
        statuses = {dict(r)["node_id"]: dict(r)["status"] for r in ne_rows}
        assert statuses == {"n1": "success", "n2": "error", "n3": "pending"}
        assert dict(ne_rows[1])["error"] == "API timeout"

    def test_single_node_execution(self, db, insert_pipeline, insert_execution):
        nodes = [{"id": "n1", "type": "input_node", "label": "Input"}]
        pid = insert_pipeline(nodes=nodes)

        logs = [{"node_id": "n1", "node_label": "Input", "node_type": "input_node", "status": "success"}]
        eid, _ = insert_execution(pid, node_logs=logs, trigger_type="single_node")

        exec_row = db.execute("SELECT trigger_type FROM pipeline_executions WHERE id = ?", (eid,)).fetchone()
        assert dict(exec_row)["trigger_type"] == "single_node"

    def test_re_execution_preserves_history(self, db, insert_pipeline, insert_execution):
        nodes = [{"id": "n1", "type": "input_node", "label": "Input"}]
        pid = insert_pipeline(nodes=nodes)

        # First execution
        logs = [{"node_id": "n1", "node_label": "Input", "node_type": "input_node", "status": "success"}]
        eid1, _ = insert_execution(pid, node_logs=logs, status="completed")

        # Second execution
        eid2, _ = insert_execution(pid, node_logs=logs, status="completed")

        exec_count = db.execute(
            "SELECT COUNT(*) as cnt FROM pipeline_executions WHERE pipeline_id = ?", (pid,)
        ).fetchone()
        assert dict(exec_count)["cnt"] == 2
        assert eid1 != eid2

    def test_execution_cancellation(self, db, insert_pipeline, insert_execution):
        nodes = [{"id": "n1", "type": "input_node", "label": "Input"}]
        pid = insert_pipeline(nodes=nodes)

        eid, _ = insert_execution(pid, status="stopped")
        exec_row = db.execute("SELECT status FROM pipeline_executions WHERE id = ?", (eid,)).fetchone()
        assert dict(exec_row)["status"] == "stopped"

    def test_timing_fields(self, db, insert_pipeline, insert_execution):
        nodes = [{"id": "n1", "type": "input_node", "label": "Input"}]
        pid = insert_pipeline(nodes=nodes)

        started = datetime.now(timezone.utc)
        completed = started + timedelta(seconds=5)
        logs = [{
            "node_id": "n1", "node_label": "Input", "node_type": "input_node",
            "status": "success",
            "started_at": started.isoformat(),
            "completed_at": completed.isoformat(),
            "duration_ms": 5000,
        }]
        eid, _ = insert_execution(pid, node_logs=logs)

        row = db.execute(
            "SELECT started_at, completed_at, duration_ms FROM pipeline_node_executions WHERE execution_id = ?",
            (eid,),
        ).fetchone()
        d = dict(row)
        assert d["duration_ms"] == 5000
        assert d["started_at"] is not None
        assert d["completed_at"] is not None


# -----------------------------------------------------------------------
# 5. HTTP Request/Response Tracking
# -----------------------------------------------------------------------

class TestHTTPTracking:
    """Request/response data stored per node execution."""

    def test_api_node_stores_request_response(self, db, insert_pipeline, insert_execution):
        nodes = [{"id": "n1", "type": "rfdiffusion_node", "label": "RF"}]
        pid = insert_pipeline(nodes=nodes)

        logs = [{
            "node_id": "n1", "node_label": "RF", "node_type": "rfdiffusion_node",
            "status": "success",
            "request_method": "POST",
            "request_url": "https://api.nims.nvidia.com/rfdiffusion",
            "request_headers": {"Authorization": "Bearer xxx", "Content-Type": "application/json"},
            "request_body": {"contigs": "50-100", "num_designs": 2},
            "response_status": 200,
            "response_status_text": "OK",
            "response_headers": {"Content-Type": "application/json"},
            "response_data": {"job_id": "j123", "file_id": "f456"},
        }]
        eid, _ = insert_execution(pid, node_logs=logs)

        row = db.execute(
            "SELECT * FROM pipeline_node_executions WHERE execution_id = ?", (eid,)
        ).fetchone()
        d = dict(row)
        assert d["request_method"] == "POST"
        assert d["request_url"] == "https://api.nims.nvidia.com/rfdiffusion"
        assert json.loads(d["request_headers"])["Content-Type"] == "application/json"
        assert json.loads(d["request_body"])["contigs"] == "50-100"
        assert d["response_status"] == 200
        assert json.loads(d["response_data"])["job_id"] == "j123"

    def test_timeout_response_captured(self, db, insert_pipeline, insert_execution):
        nodes = [{"id": "n1", "type": "rfdiffusion_node", "label": "RF"}]
        pid = insert_pipeline(nodes=nodes)

        logs = [{
            "node_id": "n1", "node_label": "RF", "node_type": "rfdiffusion_node",
            "status": "error",
            "request_method": "POST",
            "request_url": "https://api.nims.nvidia.com/rfdiffusion",
            "response_status": 504,
            "response_status_text": "Gateway Timeout",
            "error": "Request timed out after 120s",
        }]
        eid, _ = insert_execution(pid, node_logs=logs)

        row = db.execute(
            "SELECT response_status, response_status_text, error FROM pipeline_node_executions WHERE execution_id = ?",
            (eid,),
        ).fetchone()
        d = dict(row)
        assert d["response_status"] == 504
        assert d["response_status_text"] == "Gateway Timeout"
        assert "timed out" in d["error"]

    def test_non_api_nodes_have_null_request_fields(self, db, insert_pipeline, insert_execution):
        nodes = [{"id": "n1", "type": "input_node", "label": "Input"}]
        pid = insert_pipeline(nodes=nodes)

        logs = [{"node_id": "n1", "node_label": "Input", "node_type": "input_node", "status": "success"}]
        eid, _ = insert_execution(pid, node_logs=logs)

        row = db.execute(
            "SELECT request_method, request_url, response_status FROM pipeline_node_executions WHERE execution_id = ?",
            (eid,),
        ).fetchone()
        d = dict(row)
        assert d["request_method"] is None
        assert d["request_url"] is None
        assert d["response_status"] is None


# -----------------------------------------------------------------------
# 6. File Tracking
# -----------------------------------------------------------------------

class TestFileTracking:
    """File references in pipeline_node_files."""

    def test_input_node_file(self, db, seed_user, insert_pipeline):
        # Create a user_file first
        file_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO user_files (id, user_id, file_type, original_filename, stored_path) VALUES (?, ?, ?, ?, ?)",
            (file_id, seed_user, "upload", "test.pdb", f"storage/{seed_user}/uploads/pdb/{file_id}.pdb"),
        )
        db.commit()

        nodes = [{"id": "n1", "type": "input_node", "label": "Input", "config": {"filename": "test.pdb", "file_id": file_id}}]
        pid = insert_pipeline(nodes=nodes)

        # Insert file ref
        db.execute(
            """INSERT INTO pipeline_node_files (id, pipeline_id, node_id, role, file_type, filename, file_id)
               VALUES (?, ?, ?, 'input', 'pdb', 'test.pdb', ?)""",
            (str(uuid.uuid4()), pid, "n1", file_id),
        )
        db.commit()

        rows = db.execute(
            "SELECT * FROM pipeline_node_files WHERE pipeline_id = ? AND node_id = ?",
            (pid, "n1"),
        ).fetchall()
        assert len(rows) == 1
        assert dict(rows[0])["role"] == "input"
        assert dict(rows[0])["file_id"] == file_id

    def test_output_file_with_execution(self, db, seed_user, insert_pipeline, insert_execution):
        nodes = [{"id": "n1", "type": "rfdiffusion_node", "label": "RF"}]
        pid = insert_pipeline(nodes=nodes)

        logs = [{"node_id": "n1", "node_label": "RF", "node_type": "rfdiffusion_node", "status": "success"}]
        eid, ne_ids = insert_execution(pid, node_logs=logs, status="completed")

        # Insert output file ref
        db.execute(
            """INSERT INTO pipeline_node_files
               (id, pipeline_id, node_id, execution_id, node_execution_id, role, file_type, filename, file_path)
               VALUES (?, ?, ?, ?, ?, 'output', 'pdb', 'design_1.pdb', '/storage/results/design_1.pdb')""",
            (str(uuid.uuid4()), pid, "n1", eid, ne_ids[0]),
        )
        db.commit()

        rows = db.execute(
            "SELECT * FROM pipeline_node_files WHERE pipeline_id = ? AND role = 'output'", (pid,)
        ).fetchall()
        assert len(rows) == 1
        assert dict(rows[0])["execution_id"] == eid
        assert dict(rows[0])["filename"] == "design_1.pdb"

    def test_file_lineage_across_pipeline(self, db, seed_user, insert_pipeline, insert_execution):
        nodes = [
            {"id": "n1", "type": "input_node", "label": "Input"},
            {"id": "n2", "type": "rfdiffusion_node", "label": "RF"},
        ]
        pid = insert_pipeline(nodes=nodes, edges=[{"source": "n1", "target": "n2"}])
        eid, ne_ids = insert_execution(pid, node_logs=[
            {"node_id": "n1", "node_label": "Input", "node_type": "input_node", "status": "success"},
            {"node_id": "n2", "node_label": "RF", "node_type": "rfdiffusion_node", "status": "success"},
        ], status="completed")

        # Input file
        db.execute(
            """INSERT INTO pipeline_node_files (id, pipeline_id, node_id, role, file_type, filename)
               VALUES (?, ?, 'n1', 'input', 'pdb', 'input.pdb')""",
            (str(uuid.uuid4()), pid),
        )
        # Output file
        db.execute(
            """INSERT INTO pipeline_node_files (id, pipeline_id, node_id, execution_id, role, file_type, filename)
               VALUES (?, ?, 'n2', ?, 'output', 'pdb', 'output.pdb')""",
            (str(uuid.uuid4()), pid, eid),
        )
        db.commit()

        all_files = db.execute(
            "SELECT node_id, role, filename FROM pipeline_node_files WHERE pipeline_id = ? ORDER BY node_id",
            (pid,),
        ).fetchall()
        assert len(all_files) == 2
        files_by_role = {dict(f)["role"]: dict(f)["filename"] for f in all_files}
        assert files_by_role["input"] == "input.pdb"
        assert files_by_role["output"] == "output.pdb"

    def test_pipeline_delete_cascades_files_preserves_user_files(self, db, seed_user, insert_pipeline):
        file_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO user_files (id, user_id, file_type, original_filename, stored_path) VALUES (?, ?, ?, ?, ?)",
            (file_id, seed_user, "upload", "keep.pdb", f"storage/{seed_user}/keep.pdb"),
        )
        db.commit()

        nodes = [{"id": "n1", "type": "input_node", "label": "Input"}]
        pid = insert_pipeline(nodes=nodes)

        db.execute(
            """INSERT INTO pipeline_node_files (id, pipeline_id, node_id, role, file_type, filename, file_id)
               VALUES (?, ?, 'n1', 'input', 'pdb', 'keep.pdb', ?)""",
            (str(uuid.uuid4()), pid, file_id),
        )
        db.commit()

        # Delete pipeline - should cascade pipeline_node_files
        db.execute("DELETE FROM pipelines WHERE id = ?", (pid,))
        db.commit()

        # pipeline_node_files should be gone
        assert db.execute("SELECT * FROM pipeline_node_files WHERE pipeline_id = ?", (pid,)).fetchone() is None
        # user_files should still exist
        assert db.execute("SELECT id FROM user_files WHERE id = ?", (file_id,)).fetchone() is not None

    def test_file_role_check_constraint(self, db, insert_pipeline):
        nodes = [{"id": "n1", "type": "input_node", "label": "A"}]
        pid = insert_pipeline(nodes=nodes)

        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                """INSERT INTO pipeline_node_files (id, pipeline_id, node_id, role, file_type, filename)
                   VALUES (?, ?, 'n1', 'bad_role', 'pdb', 'x.pdb')""",
                (str(uuid.uuid4()), pid),
            )


# -----------------------------------------------------------------------
# 7. Typed Views
# -----------------------------------------------------------------------

class TestTypedViews:
    """SQL views that extract JSON config fields per node type."""

    def test_v_input_nodes(self, db, insert_pipeline):
        config = {"filename": "my.pdb", "file_id": "fid1", "atoms": 1234, "chains": ["A", "B"], "total_residues": 250}
        nodes = [{"id": "inp", "type": "input_node", "label": "Input", "config": config}]
        insert_pipeline(nodes=nodes)

        row = db.execute("SELECT * FROM v_input_nodes WHERE id = 'inp'").fetchone()
        d = dict(row)
        assert d["filename"] == "my.pdb"
        assert d["file_id"] == "fid1"
        assert d["atoms"] == 1234
        assert d["total_residues"] == 250

    def test_v_rfdiffusion_nodes(self, db, insert_pipeline):
        config = {"design_mode": "motif_scaffolding", "contigs": "A1-50/0 100-150", "hotspot_res": "A30,A31",
                  "diffusion_steps": 50, "num_designs": 3, "pdb_id": "1R42"}
        nodes = [{"id": "rf", "type": "rfdiffusion_node", "label": "RF", "config": config}]
        insert_pipeline(nodes=nodes)

        row = db.execute("SELECT * FROM v_rfdiffusion_nodes WHERE id = 'rf'").fetchone()
        d = dict(row)
        assert d["design_mode"] == "motif_scaffolding"
        assert d["contigs"] == "A1-50/0 100-150"
        assert d["num_designs"] == 3
        assert d["pdb_id"] == "1R42"

    def test_v_proteinmpnn_nodes(self, db, insert_pipeline):
        config = {"num_sequences": 8, "temperature": 0.1}
        nodes = [{"id": "mpnn", "type": "proteinmpnn_node", "label": "MPNN", "config": config}]
        insert_pipeline(nodes=nodes)

        row = db.execute("SELECT * FROM v_proteinmpnn_nodes WHERE id = 'mpnn'").fetchone()
        d = dict(row)
        assert d["num_sequences"] == 8
        assert d["temperature"] == 0.1

    def test_v_alphafold_nodes(self, db, insert_pipeline):
        config = {"recycle_count": 5, "num_relax": 2}
        nodes = [{"id": "af", "type": "alphafold_node", "label": "AF", "config": config}]
        insert_pipeline(nodes=nodes)

        row = db.execute("SELECT * FROM v_alphafold_nodes WHERE id = 'af'").fetchone()
        d = dict(row)
        assert d["recycle_count"] == 5
        assert d["num_relax"] == 2

    def test_v_openfold2_nodes(self, db, insert_pipeline):
        config = {"sequence": "MVLSPADKTNVK", "relax_prediction": True}
        nodes = [{"id": "of2", "type": "openfold2_node", "label": "OF2", "config": config}]
        insert_pipeline(nodes=nodes)

        row = db.execute("SELECT * FROM v_openfold2_nodes WHERE id = 'of2'").fetchone()
        d = dict(row)
        assert d["sequence"] == "MVLSPADKTNVK"
        assert d["relax_prediction"] == 1  # SQLite stores booleans as integers

    def test_views_filter_by_type(self, db, insert_pipeline):
        """Views should only return nodes of the correct type."""
        nodes = [
            {"id": "inp", "type": "input_node", "label": "Input"},
            {"id": "rf", "type": "rfdiffusion_node", "label": "RF"},
        ]
        insert_pipeline(nodes=nodes)

        inp_rows = db.execute("SELECT * FROM v_input_nodes").fetchall()
        rf_rows = db.execute("SELECT * FROM v_rfdiffusion_nodes").fetchall()

        inp_ids = [dict(r)["id"] for r in inp_rows]
        rf_ids = [dict(r)["id"] for r in rf_rows]

        assert "inp" in inp_ids
        assert "rf" not in inp_ids
        assert "rf" in rf_ids
        assert "inp" not in rf_ids


# -----------------------------------------------------------------------
# 8. Data Integrity / Cascades
# -----------------------------------------------------------------------

class TestDataIntegrity:
    """Foreign key cascading, orphan prevention."""

    def test_orphaned_nodes_impossible(self, db, insert_pipeline):
        """Deleting pipeline cascades all nodes."""
        nodes = [{"id": "n1", "type": "input_node", "label": "A"}]
        pid = insert_pipeline(nodes=nodes)

        db.execute("DELETE FROM pipelines WHERE id = ?", (pid,))
        db.commit()

        orphans = db.execute("SELECT * FROM pipeline_nodes WHERE pipeline_id = ?", (pid,)).fetchall()
        assert len(orphans) == 0

    def test_broken_edges_impossible(self, db, insert_pipeline):
        """Deleting a node cascades its edges."""
        nodes = [
            {"id": "a", "type": "input_node", "label": "A"},
            {"id": "b", "type": "rfdiffusion_node", "label": "B"},
        ]
        edges = [{"source": "a", "target": "b"}]
        pid = insert_pipeline(nodes=nodes, edges=edges)

        db.execute("DELETE FROM pipeline_nodes WHERE id = ? AND pipeline_id = ?", ("a", pid))
        db.commit()

        remaining = db.execute("SELECT * FROM pipeline_edges WHERE pipeline_id = ?", (pid,)).fetchall()
        assert len(remaining) == 0

    def test_file_id_set_null_on_user_file_delete(self, db, seed_user, insert_pipeline):
        """Deleting user_file sets pipeline_node_files.file_id to NULL."""
        file_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO user_files (id, user_id, file_type, original_filename, stored_path) VALUES (?, ?, ?, ?, ?)",
            (file_id, seed_user, "upload", "x.pdb", "storage/x.pdb"),
        )
        db.commit()

        nodes = [{"id": "n1", "type": "input_node", "label": "A"}]
        pid = insert_pipeline(nodes=nodes)

        pnf_id = str(uuid.uuid4())
        db.execute(
            """INSERT INTO pipeline_node_files (id, pipeline_id, node_id, role, file_type, filename, file_id)
               VALUES (?, ?, 'n1', 'input', 'pdb', 'x.pdb', ?)""",
            (pnf_id, pid, file_id),
        )
        db.commit()

        # Delete user file
        db.execute("DELETE FROM user_files WHERE id = ?", (file_id,))
        db.commit()

        row = db.execute("SELECT file_id FROM pipeline_node_files WHERE id = ?", (pnf_id,)).fetchone()
        assert dict(row)["file_id"] is None

    def test_execution_cascade_deletes_node_executions(self, db, insert_pipeline, insert_execution):
        nodes = [{"id": "n1", "type": "input_node", "label": "A"}]
        pid = insert_pipeline(nodes=nodes)

        logs = [{"node_id": "n1", "node_label": "A", "node_type": "input_node", "status": "success"}]
        eid, _ = insert_execution(pid, node_logs=logs)

        # Delete execution
        db.execute("DELETE FROM pipeline_executions WHERE id = ?", (eid,))
        db.commit()

        remaining = db.execute(
            "SELECT * FROM pipeline_node_executions WHERE execution_id = ?", (eid,)
        ).fetchall()
        assert len(remaining) == 0

    def test_pipeline_delete_cascades_executions(self, db, insert_pipeline, insert_execution):
        nodes = [{"id": "n1", "type": "input_node", "label": "A"}]
        pid = insert_pipeline(nodes=nodes)

        eid, _ = insert_execution(pid, node_logs=[
            {"node_id": "n1", "node_label": "A", "node_type": "input_node", "status": "success"},
        ])

        db.execute("DELETE FROM pipelines WHERE id = ?", (pid,))
        db.commit()

        assert db.execute("SELECT * FROM pipeline_executions WHERE pipeline_id = ?", (pid,)).fetchone() is None
        assert db.execute("SELECT * FROM pipeline_node_executions WHERE pipeline_id = ?", (pid,)).fetchone() is None


# -----------------------------------------------------------------------
# 9. Edge Cases
# -----------------------------------------------------------------------

class TestEdgeCases:
    """Corner cases and stress tests."""

    def test_empty_pipeline_save_load(self, db, insert_pipeline):
        pid = insert_pipeline(name="Empty")
        nodes = db.execute("SELECT * FROM pipeline_nodes WHERE pipeline_id = ?", (pid,)).fetchall()
        edges = db.execute("SELECT * FROM pipeline_edges WHERE pipeline_id = ?", (pid,)).fetchall()
        assert len(nodes) == 0
        assert len(edges) == 0

    def test_large_linear_pipeline(self, db, insert_pipeline):
        """50-node linear pipeline."""
        n = 50
        nodes = [{"id": f"n{i}", "type": "input_node" if i == 0 else "rfdiffusion_node", "label": f"Node {i}"}
                 for i in range(n)]
        edges = [{"source": f"n{i}", "target": f"n{i+1}"} for i in range(n - 1)]

        pid = insert_pipeline(nodes=nodes, edges=edges)

        node_count = db.execute(
            "SELECT COUNT(*) as cnt FROM pipeline_nodes WHERE pipeline_id = ?", (pid,)
        ).fetchone()
        edge_count = db.execute(
            "SELECT COUNT(*) as cnt FROM pipeline_edges WHERE pipeline_id = ?", (pid,)
        ).fetchone()
        assert dict(node_count)["cnt"] == n
        assert dict(edge_count)["cnt"] == n - 1

    def test_special_characters_in_pipeline_name(self, db, seed_user):
        """SQL injection prevention via parameterized queries."""
        names = [
            "'; DROP TABLE pipelines; --",
            'Pipeline with "quotes"',
            "Emoji pipeline 🧬🔬",
            "Unicode: Ñoño → π",
            "Null bytes: \x00\x01\x02",
        ]
        for name in names:
            pid = make_pipeline_id()
            db.execute(
                "INSERT INTO pipelines (id, user_id, name, status) VALUES (?, ?, ?, 'draft')",
                (pid, seed_user, name),
            )
            db.commit()

            row = db.execute("SELECT name FROM pipelines WHERE id = ?", (pid,)).fetchone()
            assert dict(row)["name"] == name

    def test_deeply_nested_json_config(self, db, insert_pipeline):
        """5+ levels of JSON nesting in config."""
        config = {
            "level1": {
                "level2": {
                    "level3": {
                        "level4": {
                            "level5": {"value": "deep", "list": [1, 2, 3]},
                        },
                    },
                },
            },
        }
        nodes = [{"id": "deep", "type": "input_node", "label": "Deep", "config": config}]
        pid = insert_pipeline(nodes=nodes)

        row = db.execute(
            "SELECT config FROM pipeline_nodes WHERE id = 'deep' AND pipeline_id = ?", (pid,)
        ).fetchone()
        assert json.loads(dict(row)["config"]) == config

    def test_null_result_metadata(self, db, insert_pipeline):
        nodes = [{"id": "n1", "type": "input_node", "label": "A"}]
        pid = insert_pipeline(nodes=nodes)

        row = db.execute(
            "SELECT result_metadata FROM pipeline_nodes WHERE id = 'n1' AND pipeline_id = ?", (pid,)
        ).fetchone()
        assert dict(row)["result_metadata"] is None

    def test_empty_config_default(self, db, seed_user):
        """Default config should be '{}'."""
        pid = make_pipeline_id()
        db.execute(
            "INSERT INTO pipelines (id, user_id, name) VALUES (?, ?, 'X')", (pid, seed_user)
        )
        db.execute(
            "INSERT INTO pipeline_nodes (id, pipeline_id, type, label) VALUES (?, ?, 'input_node', 'A')",
            ("def", pid),
        )
        db.commit()

        row = db.execute(
            "SELECT config, inputs FROM pipeline_nodes WHERE id = 'def' AND pipeline_id = ?", (pid,)
        ).fetchone()
        d = dict(row)
        assert json.loads(d["config"]) == {}
        assert json.loads(d["inputs"]) == {}

    def test_concurrent_pipelines_same_user(self, db, insert_pipeline):
        """Multiple pipelines for the same user."""
        pids = [insert_pipeline(name=f"Pipeline {i}") for i in range(5)]
        assert len(set(pids)) == 5

        count = db.execute("SELECT COUNT(*) as cnt FROM pipelines").fetchone()
        assert dict(count)["cnt"] == 5

    def test_execution_status_check_constraint(self, db, seed_user):
        pid = make_pipeline_id()
        db.execute("INSERT INTO pipelines (id, user_id, name) VALUES (?, ?, 'X')", (pid, seed_user))
        db.commit()

        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO pipeline_executions (id, pipeline_id, user_id, status) VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), pid, seed_user, "invalid_exec_status"),
            )

    def test_node_status_check_constraint(self, db, insert_pipeline):
        pid = insert_pipeline()
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                """INSERT INTO pipeline_nodes (id, pipeline_id, type, label, status)
                   VALUES (?, ?, 'input_node', 'Bad', 'bad_status')""",
                ("bad_node", pid),
            )

    def test_trigger_type_check_constraint(self, db, seed_user):
        pid = make_pipeline_id()
        db.execute("INSERT INTO pipelines (id, user_id, name) VALUES (?, ?, 'X')", (pid, seed_user))
        db.commit()

        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO pipeline_executions (id, pipeline_id, user_id, status, trigger_type) VALUES (?, ?, ?, 'running', ?)",
                (str(uuid.uuid4()), pid, seed_user, "bad_trigger"),
            )
