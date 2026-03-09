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
async def test_predict_empty_sequence_returns_sequence_empty_error():
    from agents.handlers.esmfold import ESMFoldHandler

    handler = ESMFoldHandler()

    result = await handler.process_predict_request(sequence="", user_id="u1")

    assert result["status"] == "error"
    assert result["code"] == "SEQUENCE_EMPTY"
