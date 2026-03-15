# ESMFold Tool Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add ESMFold structure prediction via NVIDIA Health API as a full-stack tool — NIM client, handler, REST routes, agent registration — following the exact same pattern as OpenFold2.

**Architecture:** ESMFold is a blocking/synchronous NIM call (like OpenFold2), not a background job (unlike AlphaFold/RFdiffusion). The NVIDIA endpoint accepts a single amino acid sequence and returns a PDB string inside a `pdbs` array. We create a 4-layer stack: NIM client → handler → REST routes → agent registry.

**Tech Stack:** Python 3.11+, FastAPI, aiohttp (async HTTP), NVIDIA Health API (`https://health.api.nvidia.com/v1/biology/nvidia/esmfold`), env vars `NVCF_RUN_KEY` / `NVIDIA_API_KEY`.

---

## Critical File Reference

Before starting, understand these existing files as templates:

| Template File | ESMFold Equivalent |
|---|---|
| `server/tools/nvidia/openfold2_client.py` | `server/tools/nvidia/esmfold_client.py` |
| `server/agents/handlers/openfold2.py` | `server/agents/handlers/esmfold.py` |
| `server/agents/prompts/openfold2.py` | `server/agents/prompts/esmfold.py` |
| `server/api/routes/openfold2.py` | `server/api/routes/esmfold.py` |

**NVIDIA ESMFold API:**
- URL: `https://health.api.nvidia.com/v1/biology/nvidia/esmfold`
- Method: POST
- Auth: `Bearer $NVCF_RUN_KEY` (or `NVIDIA_API_KEY`)
- Payload: `{"sequence": "AMINO_ACID_STRING"}`
- Response: `{"pdbs": ["ATOM  1  N   ...\n..."]}`
- Max sequence length: 400 residues (ESMFold limitation on NIM)
- Sync/blocking: returns result immediately, no polling

---

## Task 1: NIM API Client

**Files:**
- Create: `server/tools/nvidia/esmfold_client.py`

**Step 1: Write the failing test**

Create `server/tools/nvidia/test_esmfold_client.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import os

# Ensure env var is set before import
os.environ.setdefault("NVCF_RUN_KEY", "test-key")

from tools.nvidia.esmfold_client import ESMFoldClient


def test_validate_sequence_empty():
    client = ESMFoldClient(api_key="test")
    valid, msg = client.validate_sequence("")
    assert not valid
    assert "empty" in msg.lower()


def test_validate_sequence_too_short():
    client = ESMFoldClient(api_key="test")
    valid, msg = client.validate_sequence("MKT")
    assert not valid
    assert "short" in msg.lower()


def test_validate_sequence_too_long():
    client = ESMFoldClient(api_key="test")
    valid, msg = client.validate_sequence("A" * 401)
    assert not valid
    assert "400" in msg


def test_validate_sequence_invalid_chars():
    client = ESMFoldClient(api_key="test")
    valid, msg = client.validate_sequence("MKTXYZ")
    assert not valid
    assert "invalid" in msg.lower()


def test_validate_sequence_valid():
    client = ESMFoldClient(api_key="test")
    valid, clean = client.validate_sequence("MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQFEVVHSLAKWKRQTLGQHDFSAGEGLYTHMKALRPDEDRLSPLHSVYVDQWDWERVMGDGERQFSTLKSTVEAIWAGIKATEAAVSEEFGLAPFLPDQIHFVHSQELLSRYPDLDAKGRERAIAKDLGAVFLVGIGGKLSDGHRHDVRAPDYDDWSTPSELGHAGLNGDILVWNPVLEDAFELSSMGIRVDADTLKHQLALTGDEDRLELEWHQALLRGEMPQTIGGGIGQSRLTMLLLQLPHIGQVQAGVWPAAVRESVPSLL")
    assert valid
    assert isinstance(clean, str)


def test_missing_api_key():
    with pytest.raises(ValueError, match="NVCF_RUN_KEY"):
        ESMFoldClient(api_key="")


def test_extract_pdb_from_result_pdbs_array():
    client = ESMFoldClient(api_key="test")
    pdb = client.extract_pdb_from_result({"pdbs": ["ATOM  1  N   MET A   1       1.000   2.000   3.000\n"]})
    assert pdb is not None
    assert "ATOM" in pdb


def test_extract_pdb_from_result_empty():
    client = ESMFoldClient(api_key="test")
    pdb = client.extract_pdb_from_result({})
    assert pdb is None
```

**Step 2: Run test to confirm it fails**

```bash
cd server && python -m pytest tools/nvidia/test_esmfold_client.py -v
```
Expected: `ModuleNotFoundError` or `ImportError` (file doesn't exist yet).
lkkljkkjkk
**Step 3: Write the client**

Create `server/tools/nvidia/esmfold_client.py`:

```python
#!/usr/bin/env python3
"""
NVIDIA NIM API client for ESMFold protein structure prediction.
ESMFold uses ESM-2 language model — no MSA or templates required.
Blocking/synchronous: submit sequence, receive PDB immediately.
"""

import asyncio
import logging
import os
import ssl
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import aiohttp

try:
    import certifi
except ImportError:
    certifi = None

logger = logging.getLogger(__name__)

# Valid amino acid single-letter codes
VALID_AA = set("ACDEFGHIKLMNPQRSTVWY")

# ESMFold NIM limits
MAX_SEQUENCE_LENGTH = 400
MIN_SEQUENCE_LENGTH = 6


class ESMFoldClient:
    """Client for NVIDIA ESMFold NIM API (synchronous prediction, no MSA needed)."""

    def __init__(self, api_key: Optional[str] = None):
        raw_key = (
            api_key
            or os.getenv("NVCF_RUN_KEY")
            or os.getenv("NVIDIA_API_KEY")
            or ""
        )
        self.api_key = raw_key.strip()
        if not self.api_key:
            raise ValueError(
                "NVCF_RUN_KEY or NVIDIA_API_KEY environment variable required. "
                "Get your key at https://build.nvidia.com/nvidia/esmfold"
            )

        self.base_url = (
            os.getenv("ESMFOLD_URL")
            or "https://health.api.nvidia.com/v1/biology/nvidia/esmfold"
        )
        self.timeout = int(os.getenv("ESMFOLD_TIMEOUT", "120"))  # 2 min default

        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

    def validate_sequence(self, sequence: str) -> Tuple[bool, str]:
        """Validate protein sequence. ESMFold NIM: 6–400 residues, standard AA only."""
        if not sequence or not sequence.strip():
            return False, "Sequence cannot be empty"

        clean = "".join(sequence.split()).upper()

        invalid = set(clean) - VALID_AA
        if invalid:
            return False, f"Invalid amino acids: {', '.join(sorted(invalid))}"

        if len(clean) < MIN_SEQUENCE_LENGTH:
            return False, f"Sequence too short ({len(clean)} residues). Minimum: {MIN_SEQUENCE_LENGTH}"

        if len(clean) > MAX_SEQUENCE_LENGTH:
            return (
                False,
                f"Sequence exceeds {MAX_SEQUENCE_LENGTH} residues ({len(clean)}). "
                "ESMFold NIM supports up to 400 residues. Use AlphaFold2 or OpenFold2 for longer sequences.",
            )

        return True, clean

    def build_payload(self, sequence: str) -> Dict[str, Any]:
        """Build ESMFold request payload."""
        return {"sequence": sequence}

    def extract_pdb_from_result(self, result_data: Dict[str, Any]) -> Optional[str]:
        """Extract PDB string from ESMFold API response.
        NVIDIA ESMFold returns: {"pdbs": ["ATOM ...\n..."]}
        """
        try:
            if not isinstance(result_data, dict):
                return None

            # Primary: NVIDIA ESMFold response format
            pdbs = result_data.get("pdbs")
            if pdbs and isinstance(pdbs, list) and pdbs[0]:
                first = pdbs[0]
                if isinstance(first, str) and first.strip():
                    return first

            # Fallback: common PDB key names
            for key in ("pdb", "structure", "pdb_string", "pdb_content"):
                val = result_data.get(key)
                if isinstance(val, str) and val.strip().startswith(("ATOM", "HEADER", "REMARK")):
                    return val

            logger.warning("Could not extract PDB from ESMFold result keys: %s", list(result_data.keys()))
            return None
        except Exception as e:
            logger.error("Error extracting PDB from ESMFold result: %s", e)
            return None

    async def predict(self, sequence: str) -> Dict[str, Any]:
        """
        Submit synchronous structure prediction to ESMFold NIM.

        Args:
            sequence: Validated amino acid sequence (≤400 residues)

        Returns:
            Dict with status ("completed" | "timeout" | "request_failed" | "exception")
            and data (containing PDB) or error message.
        """
        is_valid, result = self.validate_sequence(sequence)
        if not is_valid:
            return {"status": "validation_failed", "error": result}

        clean_sequence = result
        payload = self.build_payload(clean_sequence)

        logger.info("ESMFold request: url=%s sequence_len=%s", self.base_url, len(clean_sequence))

        try:
            ssl_context = ssl.create_default_context()
            if certifi:
                try:
                    ssl_context.load_verify_locations(certifi.where())
                except Exception:
                    pass

            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    self.base_url,
                    headers=self.headers,
                    json=payload,
                    ssl=ssl_context,
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {"status": "completed", "data": data}
                    else:
                        text = await response.text()
                        logger.warning("ESMFold API HTTP %s: %s", response.status, text[:500])
                        return {
                            "status": "request_failed",
                            "error": f"HTTP {response.status}: {text[:500]}" + ("..." if len(text) > 500 else ""),
                            "http_status": response.status,
                        }
        except asyncio.TimeoutError:
            return {"status": "timeout", "error": "Prediction timed out. Try a shorter sequence."}
        except Exception as e:
            logger.exception("ESMFold API request failed")
            return {"status": "exception", "error": str(e)}

    def save_pdb_file(self, pdb_content: str, filename: str) -> str:
        """Save PDB content to esmfold_results folder."""
        base_dir = Path(__file__).parent
        results_dir = base_dir / "esmfold_results"
        results_dir.mkdir(exist_ok=True)
        filepath = results_dir / filename
        filepath.write_text(pdb_content, encoding="utf-8")
        return str(filepath.relative_to(base_dir))
```

**Step 4: Run tests**

```bash
cd server && python -m pytest tools/nvidia/test_esmfold_client.py -v
```
Expected: All 8 tests PASS.

**Step 5: Commit**

```bash
git add server/tools/nvidia/esmfold_client.py server/tools/nvidia/test_esmfold_client.py
git commit -m "feat: add ESMFold NIM client with validation and PDB extraction"
```

---

## Task 2: Agent Handler

**Files:**
- Create: `server/agents/handlers/esmfold.py`

**Step 1: Write the failing test**

Create `server/agents/handlers/test_esmfold_handler.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import os

os.environ.setdefault("NVCF_RUN_KEY", "test-key")


@pytest.mark.asyncio
async def test_predict_returns_completed_on_success():
    from agents.handlers.esmfold import ESMFoldHandler

    handler = ESMFoldHandler()

    mock_client = MagicMock()
    mock_client.validate_sequence.return_value = (True, "MKTAY")
    mock_client.predict = AsyncMock(return_value={
        "status": "completed",
        "data": {"pdbs": ["ATOM  1  N   MET A   1       0.000   0.000   0.000\n"]},
    })
    mock_client.extract_pdb_from_result.return_value = "ATOM  1  N   MET A   1       0.000   0.000   0.000\n"
    mock_client.save_pdb_file.return_value = "esmfold_results/esmfold_test-id.pdb"

    handler.client = mock_client

    with patch("agents.handlers.esmfold.save_result_file", return_value="storage/user/esmfold_results/test.pdb"):
        with patch("agents.handlers.esmfold.associate_file_with_session"):
            result = await handler.process_predict_request(
                sequence="MKTAY",
                job_id="test-id",
                session_id="sess-1",
                user_id="user-1",
            )

    assert result["status"] == "completed"
    assert "pdbContent" in result
    assert result["job_id"] == "test-id"
    assert "/api/esmfold/result/test-id" in result["pdb_url"]


@pytest.mark.asyncio
async def test_predict_returns_error_on_api_failure():
    from agents.handlers.esmfold import ESMFoldHandler

    handler = ESMFoldHandler()

    mock_client = MagicMock()
    mock_client.validate_sequence.return_value = (True, "MKTAY")
    mock_client.predict = AsyncMock(return_value={
        "status": "request_failed",
        "error": "HTTP 422: bad sequence",
    })

    handler.client = mock_client

    result = await handler.process_predict_request(sequence="MKTAY", user_id="u1")

    assert result["status"] == "error"
    assert "code" in result


@pytest.mark.asyncio
async def test_predict_validates_sequence_before_api_call():
    from agents.handlers.esmfold import ESMFoldHandler

    handler = ESMFoldHandler()

    result = await handler.process_predict_request(sequence="", user_id="u1")

    assert result["status"] == "error"
    assert result["code"] == "SEQUENCE_EMPTY"
```

**Step 2: Run test to confirm it fails**

```bash
cd server && python -m pytest agents/handlers/test_esmfold_handler.py -v
```
Expected: `ModuleNotFoundError` (handler doesn't exist).

**Step 3: Write the handler**

Create `server/agents/handlers/esmfold.py`:

```python
#!/usr/bin/env python3
"""
ESMFold request handler for the server.
ESMFold uses ESM-2 language model — no MSA or templates required.
Blocking/synchronous flow: submit sequence, receive PDB immediately.
"""

import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

_server_dir = Path(__file__).resolve().parent.parent.parent
if str(_server_dir) not in sys.path:
    sys.path.insert(0, str(_server_dir))

try:
    from ...tools.nvidia.esmfold_client import ESMFoldClient
    from ...domain.storage.file_access import save_result_file
    from ...domain.storage.session_tracker import associate_file_with_session
except ImportError:
    from tools.nvidia.esmfold_client import ESMFoldClient
    from domain.storage.file_access import save_result_file
    from domain.storage.session_tracker import associate_file_with_session

logger = logging.getLogger(__name__)


class ESMFoldHandler:
    """Handles ESMFold structure prediction requests (blocking, no MSA needed)."""

    def __init__(self):
        self.client: Optional[ESMFoldClient] = None
        self.job_results: Dict[str, Dict[str, Any]] = {}

    def _get_client(self) -> ESMFoldClient:
        if self.client is None:
            try:
                self.client = ESMFoldClient()
            except ValueError as e:
                logger.error("ESMFold API configuration error: %s", e)
                raise ValueError(
                    "ESMFold requires NVCF_RUN_KEY or NVIDIA_API_KEY. "
                    "Get your key at https://build.nvidia.com/nvidia/esmfold"
                )
        return self.client

    async def process_predict_request(
        self,
        sequence: str,
        job_id: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process ESMFold prediction request (blocking).

        Args:
            sequence: Protein amino acid sequence (required, ≤400 residues)
            job_id: Client-provided job ID for storage and retrieval
            session_id: Chat session for file association
            user_id: User ID for storage isolation

        Returns:
            Dict with status, job_id, pdb_url, pdbContent, or error+code
        """
        job_id = job_id or str(uuid.uuid4())
        user_id = user_id or "system"

        # Early sequence validation before initializing client
        try:
            client = self._get_client()
        except ValueError as e:
            return {"status": "error", "error": str(e), "code": "API_KEY_MISSING"}

        is_valid, msg = client.validate_sequence(sequence)
        if not is_valid:
            code = "SEQUENCE_EMPTY" if not sequence or not sequence.strip() else "SEQUENCE_INVALID"
            if "short" in msg.lower():
                code = "SEQUENCE_TOO_SHORT"
            if "400" in msg or "exceed" in msg.lower():
                code = "SEQUENCE_TOO_LONG"
            return {"status": "error", "error": msg, "code": code}

        try:
            result = await client.predict(sequence=sequence)
        except Exception as e:
            logger.exception("ESMFold predict raised")
            return {"status": "error", "error": str(e), "code": "API_ERROR"}

        if result.get("status") == "completed":
            data = result.get("data", {})
            pdb_content = client.extract_pdb_from_result(data)

            if not pdb_content:
                logger.warning("ESMFold: No PDB in response. Keys: %s", list(data.keys()) if isinstance(data, dict) else type(data))
                return {
                    "status": "error",
                    "error": "No PDB content in API response; unexpected response format",
                    "code": "API_ERROR",
                }

            filename = f"esmfold_{job_id}.pdb"
            stored_path = None

            try:
                stored_path = save_result_file(
                    user_id=user_id,
                    file_id=job_id,
                    file_type="esmfold",
                    filename=filename,
                    content=pdb_content.encode("utf-8"),
                    job_id=job_id,
                    metadata={"sequence_length": len(sequence.strip())},
                )
                try:
                    client.save_pdb_file(pdb_content, filename)
                except Exception as e:
                    logger.warning("Failed to save ESMFold result to esmfold_results folder: %s", e)
            except Exception as e:
                logger.error("Failed to save ESMFold result: %s", e)

            if session_id and user_id and stored_path:
                try:
                    associate_file_with_session(
                        session_id=str(session_id),
                        file_id=job_id,
                        user_id=user_id,
                        file_type="esmfold",
                        file_path=stored_path,
                        filename=filename,
                        size=len(pdb_content),
                        job_id=job_id,
                        metadata={"sequence_length": len(sequence.strip())},
                    )
                except Exception as e:
                    logger.warning("Failed to associate ESMFold file with session: %s", e)

            self.job_results[job_id] = {
                "pdbContent": pdb_content,
                "filename": filename,
                "stored_path": stored_path,
            }

            return {
                "status": "completed",
                "job_id": job_id,
                "pdb_url": f"/api/esmfold/result/{job_id}" if stored_path else None,
                "pdbContent": pdb_content,
                "message": "Structure predicted successfully",
            }

        if result.get("status") == "timeout":
            return {
                "status": "error",
                "error": result.get("error", "Prediction timed out"),
                "code": "TIMEOUT",
            }

        if result.get("status") == "validation_failed":
            return {"status": "error", "error": result.get("error", "Invalid sequence"), "code": "SEQUENCE_INVALID"}

        return {
            "status": "error",
            "error": result.get("error", "Prediction failed"),
            "code": "API_ERROR",
        }

    def get_result(self, job_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get cached result by job_id."""
        return self.job_results.get(job_id)


esmfold_handler = ESMFoldHandler()
```

**Step 4: Run tests**

```bash
cd server && python -m pytest agents/handlers/test_esmfold_handler.py -v
```
Expected: All 3 tests PASS.

**Step 5: Commit**

```bash
git add server/agents/handlers/esmfold.py server/agents/handlers/test_esmfold_handler.py
git commit -m "feat: add ESMFold handler with blocking prediction and user-scoped storage"
```

---

## Task 3: System Prompt

**Files:**
- Create: `server/agents/prompts/esmfold.py`

**Step 1: No test needed** (string constant, no logic).

**Step 2: Write the prompt**

Create `server/agents/prompts/esmfold.py`:

```python
ESMFOLD_AGENT_SYSTEM_PROMPT = """You are an ESMFold structure prediction assistant.

ESMFold uses Meta's ESM-2 protein language model to predict 3D protein structure from sequence alone — no MSA or templates required. This makes it extremely fast (seconds vs. minutes for AlphaFold2).

**When to use ESMFold:**
- Fast structure prediction needed (seconds, not minutes)
- Short to medium proteins (≤400 residues)
- No MSA data available
- Exploratory/screening tasks before more expensive methods

**Limitations:**
- Max 400 residues (use AlphaFold2 or OpenFold2 for longer sequences)
- Lower accuracy than AlphaFold2 for complex proteins
- No template or MSA support (by design — ESM-2 is the "MSA")

**Your role:**
1. Extract the protein sequence from the user's request
2. Validate it is a standard amino acid sequence
3. Confirm the prediction parameters with the user before running
4. Report the result with the predicted structure URL

**Response format when triggering prediction:**
Always return JSON with:
- action: "esmfold_predict"
- sequence: <the sequence>
- jobId: <uuid>
- sessionId: <session id if available>

Do NOT make up sequences. If the user provides a PDB ID or protein name, explain that you need the actual amino acid sequence.
"""
```

**Step 3: Commit**

```bash
git add server/agents/prompts/esmfold.py
git commit -m "feat: add ESMFold agent system prompt"
```

---

## Task 4: REST Routes

**Files:**
- Create: `server/api/routes/esmfold.py`

**Step 1: Write the failing test**

Create `server/api/routes/test_esmfold_routes.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
import os

os.environ.setdefault("NVCF_RUN_KEY", "test-key")

# Minimal app for route testing
from fastapi import FastAPI
from api.routes import esmfold

app = FastAPI()
app.include_router(esmfold.router)


@pytest.fixture
def client():
    return TestClient(app)


def test_predict_missing_sequence(client):
    with patch("api.routes.esmfold.get_current_user", return_value={"id": "u1"}):
        response = client.post("/api/esmfold/predict", json={})
    assert response.status_code == 400
    assert "sequence" in response.json().get("error", "").lower() or response.status_code == 400


def test_predict_success(client):
    mock_result = {
        "status": "completed",
        "job_id": "test-job",
        "pdb_url": "/api/esmfold/result/test-job",
        "pdbContent": "ATOM  1  N   MET A   1\n",
        "message": "Structure predicted successfully",
    }
    with patch("api.routes.esmfold.get_current_user", return_value={"id": "u1"}):
        with patch("api.routes.esmfold.esmfold_handler") as mock_handler:
            mock_handler.process_predict_request = AsyncMock(return_value=mock_result)
            response = client.post(
                "/api/esmfold/predict",
                json={"sequence": "MKTAY", "jobId": "test-job"},
            )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert "pdbContent" in data
```

**Step 2: Run test to confirm it fails**

```bash
cd server && python -m pytest api/routes/test_esmfold_routes.py -v
```
Expected: `ModuleNotFoundError` (routes file doesn't exist).

**Step 3: Write the routes**

Create `server/api/routes/esmfold.py`:

```python
"""ESMFold structure prediction API endpoints."""

import traceback
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

try:
    from ...agents.handlers.esmfold import esmfold_handler
    from ...infrastructure.utils import log_line
    from ...api.middleware.auth import get_current_user
    from ...api.limiter import limiter, DEBUG_API
    from ...domain.storage.file_access import get_user_file_path
except ImportError:
    from agents.handlers.esmfold import esmfold_handler
    from infrastructure.utils import log_line
    from api.middleware.auth import get_current_user
    from api.limiter import limiter, DEBUG_API
    from domain.storage.file_access import get_user_file_path

router = APIRouter()


@router.post("/api/esmfold/predict")
@limiter.limit("10/minute")
async def esmfold_predict(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    """Predict protein 3D structure using ESMFold (blocking, ≤400 residues, no MSA needed)."""
    try:
        body = await request.json()
        sequence = (body.get("sequence") or "").strip()
        job_id = body.get("jobId")
        session_id = body.get("sessionId")

        if not sequence:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "error": "Missing sequence",
                    "code": "SEQUENCE_EMPTY",
                },
            )

        log_line("esmfold_predict_request", {
            "job_id": job_id,
            "user_id": user["id"],
            "session_id": session_id,
            "sequence_length": len(sequence),
        })

        result = await esmfold_handler.process_predict_request(
            sequence=sequence,
            job_id=job_id,
            session_id=session_id,
            user_id=user["id"],
        )

        if result.get("status") == "error":
            code = result.get("code", "API_ERROR")
            log_line("esmfold_predict_error", {"code": code, "error": result.get("error", "")[:500]})

            if code == "API_KEY_MISSING":
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "error",
                        "error": result.get("error", "ESMFold service not available"),
                        "code": code,
                    },
                )

            http_status = 400 if code in (
                "SEQUENCE_EMPTY", "SEQUENCE_TOO_LONG", "SEQUENCE_TOO_SHORT", "SEQUENCE_INVALID"
            ) else 502
            return JSONResponse(status_code=http_status, content=result)

        return JSONResponse(status_code=200, content=result)

    except Exception as e:
        log_line("esmfold_predict_failed", {"error": str(e), "trace": traceback.format_exc()})
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": str(e) if DEBUG_API else "An unexpected error occurred",
                "code": "INTERNAL_ERROR",
            },
        )


@router.get("/api/esmfold/result/{job_id}")
@limiter.limit("30/minute")
async def esmfold_result(request: Request, job_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    """Download the predicted PDB file. Verifies ownership."""
    try:
        file_path = get_user_file_path(job_id, user["id"])
        return FileResponse(
            file_path,
            media_type="chemical/x-pdb",
            filename=f"esmfold_{job_id}.pdb",
        )
    except HTTPException as exc:
        raise exc
    except Exception as e:
        log_line("esmfold_result_failed", {"error": str(e), "job_id": job_id})
        raise HTTPException(status_code=404, detail="ESMFold result not found")
```

**Step 4: Run tests**

```bash
cd server && python -m pytest api/routes/test_esmfold_routes.py -v
```
Expected: All tests PASS.

**Step 5: Commit**

```bash
git add server/api/routes/esmfold.py server/api/routes/test_esmfold_routes.py
git commit -m "feat: add ESMFold REST endpoints (predict + result download)"
```

---

## Task 5: Wire Into App

**Files:**
- Modify: `server/api/routes/__init__.py` — add `"esmfold"` to `__all__`
- Modify: `server/app.py` — add `esmfold` import + `app.include_router(esmfold.router)`
- Modify: `server/agents/registry.py` — add `esmfold-agent` entry + import prompt

**Step 1: Update `__init__.py`**

In `server/api/routes/__init__.py`, add `"esmfold"` to the `__all__` list:

```python
__all__ = [
    "auth", "credits", "reports", "admin", "pipelines",
    "chat_sessions", "chat_messages", "three_d_canvases", "attachments",
    "agents", "alphafold", "rfdiffusion", "proteinmpnn",
    "openfold2", "diffdock", "files", "misc", "esmfold",   # <-- add esmfold
]
```

**Step 2: Update `app.py`**

In `server/app.py`, add `esmfold` to both import blocks:

```python
# In the try block (relative imports):
from .api.routes import (
    ...
    esmfold,       # <-- add
)

# In the except block (absolute imports):
from api.routes import (
    ...
    esmfold,       # <-- add
)
```

Then add the router registration after the other new routers:
```python
app.include_router(esmfold.router)
```

**Step 3: Update `agents/registry.py`**

Add import at the top:
```python
from .prompts.esmfold import ESMFOLD_AGENT_SYSTEM_PROMPT
```

Add agent entry in the `agents` dict (after `openfold2-agent`):
```python
"esmfold-agent": {
    "id": "esmfold-agent",
    "name": "ESMFold Structure Prediction",
    "description": (
        "Predicts 3D protein structure from sequence using ESMFold (ESM-2 language model) "
        "via NVIDIA NIM. No MSA or templates required — extremely fast (seconds). "
        "Supports sequences up to 400 residues. Use for rapid screening before AlphaFold2. "
        "Use when user asks for fast folding, ESMFold, or has sequences ≤400 residues."
    ),
    "system": ESMFOLD_AGENT_SYSTEM_PROMPT,
    "modelEnv": "CLAUDE_CHAT_MODEL",
    "defaultModel": os.getenv("CLAUDE_CHAT_MODEL", "claude-3-5-sonnet-20241022"),
    "kind": "esmfold",
    "category": "fold",
},
```

**Step 4: Verify server starts**

```bash
cd "/Users/alizabista/Downloads/novoprotien-ai-main 2"
python -m uvicorn server.app:app --host 127.0.0.1 --port 18890 &
sleep 4
curl -s http://127.0.0.1:18890/api/health
# Expected: {"ok":true}
curl -s http://127.0.0.1:18890/api/agents | python3 -m json.tool | grep esmfold
# Expected: "esmfold-agent" appears in response
kill %1
```

**Step 5: Commit**

```bash
git add server/api/routes/__init__.py server/app.py server/agents/registry.py server/agents/prompts/esmfold.py
git commit -m "feat: wire ESMFold into app router and agent registry"
```

---

## Task 6: Smoke Test End-to-End

**Step 1: Test with real NVIDIA API key (if available)**

```bash
# Set your key
export NVCF_RUN_KEY=your-key-here

# Start server
cd "/Users/alizabista/Downloads/novoprotien-ai-main 2"
python -m uvicorn server.app:app --host 127.0.0.1 --port 18890 &
sleep 4
```

**Step 2: Curl the predict endpoint**

```bash
# You'll need a valid JWT — skip auth for this smoke test by checking the raw handler:
cd server && python3 -c "
import asyncio, os
os.environ['NVCF_RUN_KEY'] = os.getenv('NVCF_RUN_KEY', '')
from agents.handlers.esmfold import esmfold_handler
result = asyncio.run(esmfold_handler.process_predict_request(
    sequence='MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQFEVVHSLAKWKRQTLGQHDFSAGEGLYTHMKALRPDEDRLSPLHSVYVDQWDWERVMGDGERQFSTLK',
    job_id='smoke-test-1',
    user_id='test-user',
))
print('status:', result.get('status'))
print('has pdb:', bool(result.get('pdbContent')))
print('pdb_url:', result.get('pdb_url'))
"
```

Expected:
```
status: completed
has pdb: True
pdb_url: /api/esmfold/result/smoke-test-1
```

**Step 3: Commit smoke test note**

```bash
git commit --allow-empty -m "chore: verify ESMFold smoke test passes with real NVIDIA API key"
```

---

## Environment Variables

Add to your `.env` (server directory):

```bash
# ESMFold NIM (uses same key as AlphaFold/OpenFold2)
# NVCF_RUN_KEY=nvapi-xxxx   # already set for other tools
# Optional overrides:
# ESMFOLD_URL=https://health.api.nvidia.com/v1/biology/nvidia/esmfold
# ESMFOLD_TIMEOUT=120
```

No new key needed if `NVCF_RUN_KEY` is already set for other NIM tools.

---

## Files Created/Modified Summary

| Action | File |
|---|---|
| **Create** | `server/tools/nvidia/esmfold_client.py` |
| **Create** | `server/tools/nvidia/test_esmfold_client.py` |
| **Create** | `server/agents/handlers/esmfold.py` |
| **Create** | `server/agents/handlers/test_esmfold_handler.py` |
| **Create** | `server/agents/prompts/esmfold.py` |
| **Create** | `server/api/routes/esmfold.py` |
| **Create** | `server/api/routes/test_esmfold_routes.py` |
| **Modify** | `server/api/routes/__init__.py` — add `"esmfold"` to `__all__` |
| **Modify** | `server/app.py` — add `esmfold` import + `app.include_router` |
| **Modify** | `server/agents/registry.py` — add agent entry + prompt import |
