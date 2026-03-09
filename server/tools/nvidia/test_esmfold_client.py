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
    assert clean == clean.upper()  # validate_sequence returns uppercase
    assert " " not in clean        # validate_sequence strips whitespace
    assert len(clean) > 0


def test_missing_api_key():
    with patch.dict(os.environ, {}, clear=True):
        # Remove all possible key env vars
        env_without_keys = {k: v for k, v in os.environ.items() if k not in ("NVCF_RUN_KEY", "NVIDIA_API_KEY")}
        with patch.dict(os.environ, env_without_keys, clear=True):
            with pytest.raises(ValueError, match="NVCF_RUN_KEY"):
                ESMFoldClient(api_key=None)


def test_extract_pdb_from_result_pdbs_array():
    client = ESMFoldClient(api_key="test")
    pdb = client.extract_pdb_from_result({"pdbs": ["ATOM  1  N   MET A   1       1.000   2.000   3.000\n"]})
    assert pdb is not None
    assert "ATOM" in pdb


def test_extract_pdb_from_result_empty():
    client = ESMFoldClient(api_key="test")
    pdb = client.extract_pdb_from_result({})
    assert pdb is None
