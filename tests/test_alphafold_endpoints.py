#!/usr/bin/env python3
r"""
Test AlphaFold2 endpoints and auth separately.

Run from project root:
  python tests/test_alphafold_endpoints.py

Or with server venv (PowerShell):
  cd server; .venv\Scripts\activate; python ..\tests\test_alphafold_endpoints.py

Requires: server running on http://localhost:8787
"""

import json
import os
import sys
from pathlib import Path

# Add server to path for imports
server_dir = Path(__file__).resolve().parent.parent / "server"
sys.path.insert(0, str(server_dir))

try:
    import requests
except ImportError:
    print("Install requests: pip install requests")
    sys.exit(1)

BASE_URL = os.getenv("API_BASE", "http://localhost:8787/api")
TEST_SEQUENCE = "MVLSEGEWQLVLHVWAKVEADVAGHGQDILIRLFKSHPETLEKFDRFKHLKTEAEMKASEDLKKHGVTVLTALGAILKKKGHHEAELKPLAQSHATKHKI"


def print_section(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def get_auth_token() -> str | None:
    """Sign in and return access token."""
    url = f"{BASE_URL}/auth/signin"
    payload = {"email": "user1@gmail.com", "password": "test12345"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data.get("access_token")
    except Exception as e:
        print(f"  Signin failed: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"  Response: {e.response.text[:200]}")
        return None


def test_fold_no_auth():
    """Test POST /api/alphafold/fold without auth."""
    print_section("1. AlphaFold FOLD endpoint (no auth)")
    url = f"{BASE_URL}/alphafold/fold"
    payload = {
        "sequence": TEST_SEQUENCE,
        "jobId": "test_af_noauth_001",
        "parameters": {
            "algorithm": "mmseqs2",
            "e_value": 0.0001,
            "iterations": 1,
            "databases": ["small_bfd"],
            "relax_prediction": False,
            "skip_template_search": True,
        },
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        print(f"  Status: {r.status_code}")
        print(f"  Response: {json.dumps(r.json(), indent=2)[:500]}")
        if r.status_code == 202:
            print("  OK: Fold accepted (202)")
            return True
        if r.status_code == 401:
            print("  FAIL: Requires auth (401)")
            return False
        print(f"  FAIL: Unexpected status")
        return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def test_fold_with_auth(token: str):
    """Test POST /api/alphafold/fold with auth."""
    print_section("2. AlphaFold FOLD endpoint (with auth)")
    url = f"{BASE_URL}/alphafold/fold"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "sequence": TEST_SEQUENCE,
        "jobId": "test_af_auth_001",
        "parameters": {
            "algorithm": "mmseqs2",
            "e_value": 0.0001,
            "iterations": 1,
            "databases": ["small_bfd"],
            "relax_prediction": False,
            "skip_template_search": True,
        },
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        print(f"  Status: {r.status_code}")
        print(f"  Response: {json.dumps(r.json(), indent=2)[:500]}")
        if r.status_code == 202:
            print("  OK: Fold accepted (202)")
            return True
        if r.status_code == 401:
            print("  FAIL: Auth rejected (401)")
            return False
        print(f"  FAIL: Unexpected status")
        return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def test_status_no_auth(job_id: str = "test_af_noauth_001"):
    """Test GET /api/alphafold/status/{job_id} without auth."""
    print_section("3. AlphaFold STATUS endpoint (no auth)")
    url = f"{BASE_URL}/alphafold/status/{job_id}"
    try:
        r = requests.get(url, timeout=10)
        print(f"  Status: {r.status_code}")
        print(f"  Response: {json.dumps(r.json() if r.text else {}, indent=2)[:500]}")
        if r.status_code == 200:
            print("  OK: Status returned (200)")
            return True
        if r.status_code == 401:
            print("  FAIL: Requires auth (401)")
            return False
        if r.status_code == 404:
            print("  NOTE: 404 - job not found (expected if job never ran)")
            return True  # Endpoint works, job just doesn't exist
        print(f"  FAIL: Unexpected status")
        return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def test_status_with_auth(token: str, job_id: str = "test_af_auth_001"):
    """Test GET /api/alphafold/status/{job_id} with auth."""
    print_section("4. AlphaFold STATUS endpoint (with auth)")
    url = f"{BASE_URL}/alphafold/status/{job_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"  Status: {r.status_code}")
        print(f"  Response: {json.dumps(r.json() if r.text else {}, indent=2)[:500]}")
        if r.status_code == 200:
            print("  OK: Status returned (200)")
            return True
        if r.status_code == 401:
            print("  FAIL: Auth rejected (401)")
            return False
        if r.status_code == 404:
            print("  NOTE: 404 - job not found (expected if job never ran)")
            return True
        print(f"  FAIL: Unexpected status")
        return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def test_nvidia_api_direct():
    """Test NVIDIA NIMS API directly (requires NVCF_RUN_KEY)."""
    print_section("5. NVIDIA NIMS API (direct - optional)")
    api_key = os.getenv("NVCF_RUN_KEY")
    if not api_key:
        print("  SKIP: NVCF_RUN_KEY not set")
        return None

    base_url = os.getenv("NIMS_URL") or "https://health.api.nvidia.com/v1/biology/deepmind/alphafold2"
    status_url = os.getenv("STATUS_URL") or "https://health.api.nvidia.com/v1/status"

    print(f"  Base URL: {base_url}")
    print(f"  Status URL: {status_url}")
    print("  Submitting minimal request...")

    headers = {
        "content-type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "NVCF-POLL-SECONDS": "10",
    }
    payload = {
        "sequence": TEST_SEQUENCE[:50] + "A" * 30,  # 80 chars min
        "algorithm": "mmseqs2",
        "e_value": 0.0001,
        "iterations": 1,
        "databases": ["small_bfd"],
        "relax_prediction": False,
        "skip_template_search": True,
    }

    try:
        r = requests.post(base_url, headers=headers, json=payload, timeout=30)
        print(f"  POST Status: {r.status_code}")
        print(f"  POST Headers: {dict(r.headers)}")
        if r.status_code == 202:
            req_id = r.headers.get("nvcf-reqid")
            print(f"  Request ID: {req_id}")
            if req_id:
                poll_url = f"{status_url}/{req_id}"
                print(f"  Polling: {poll_url}")
                poll_r = requests.get(poll_url, headers=headers, timeout=15)
                print(f"  Poll Status: {poll_r.status_code}")
                print(f"  Poll Response: {poll_r.text[:300]}")
                if poll_r.status_code == 404:
                    print("  FAIL: NVIDIA status endpoint returns 404 (this is your error!)")
                    return False
        elif r.status_code == 200:
            print("  OK: Immediate completion")
            return True
        else:
            print(f"  Response: {r.text[:300]}")
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def main():
    print("\n" + "#" * 60)
    print("#  AlphaFold2 Endpoint & Auth Test")
    print("#" * 60)
    print(f"\nBase URL: {BASE_URL}")
    print("Make sure the server is running: npm run start:server")

    results = []

    # 1. Fold without auth
    results.append(("Fold (no auth)", test_fold_no_auth()))

    # 2. Get token and test with auth
    token = get_auth_token()
    if token:
        print(f"\n  Token obtained: {token[:20]}...")
        results.append(("Fold (with auth)", test_fold_with_auth(token)))
        results.append(("Status (with auth)", test_status_with_auth(token)))
    else:
        print("\n  Skipping auth tests (signin failed)")
        results.append(("Fold (with auth)", False))
        results.append(("Status (with auth)", False))

    # 3. Status without auth
    results.append(("Status (no auth)", test_status_no_auth()))

    # 4. NVIDIA API direct (optional)
    nv_result = test_nvidia_api_direct()
    if nv_result is not None:
        results.append(("NVIDIA API direct", nv_result))

    # Summary
    print_section("SUMMARY")
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        print(f"  {name}: {status}")
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\n  Total: {passed}/{total} passed")
    print("\n" + "=" * 60)

    # Interpretation
    print("\nInterpretation:")
    print("  - If Fold/Status work: Backend endpoints are OK.")
    print("  - If 401 on Fold/Status: Auth is required (add Depends(get_current_user)).")
    print("  - If NVIDIA direct returns 404 on poll: The 404 comes from NVIDIA's API,")
    print("    not your backend. Check NVIDIA API docs / endpoint URLs.")
    print()


if __name__ == "__main__":
    main()
