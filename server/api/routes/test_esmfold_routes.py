import pytest
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("NVCF_RUN_KEY", "test-key")

# Pre-mock auth middleware before importing routes (avoids relative import issues in test env)
_mock_auth = MagicMock()
_mock_auth.get_current_user = AsyncMock(return_value={"id": "u1"})
sys.modules.setdefault("api.middleware.auth", _mock_auth)

# Also mock infrastructure modules pulled in transitively
sys.modules.setdefault("infrastructure.auth", MagicMock())
sys.modules.setdefault("domain.user.service", MagicMock())

from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.routes import esmfold
from api.limiter import limiter


async def _override_user():
    return {"id": "u1"}


app = FastAPI()
app.state.limiter = limiter
app.include_router(esmfold.router)
app.dependency_overrides[esmfold.get_current_user] = _override_user


@pytest.fixture
def client():
    return TestClient(app)


def test_predict_missing_sequence(client):
    response = client.post("/api/esmfold/predict", json={})
    assert response.status_code == 400
    assert "sequence" in response.json().get("error", "").lower()


def test_predict_success(client):
    mock_result = {
        "status": "completed",
        "job_id": "test-job",
        "pdb_url": "/api/esmfold/result/test-job",
        "pdbContent": "ATOM  1  N   MET A   1\n",
        "message": "Structure predicted successfully",
    }
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
