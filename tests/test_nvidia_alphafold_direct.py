#!/usr/bin/env python3
"""Test NVIDIA AlphaFold API directly. Loads NVCF_RUN_KEY from .env."""
import os
import sys
from pathlib import Path

# Load .env from project root and server/
project_root = Path(__file__).resolve().parent.parent
from dotenv import load_dotenv
for env_path in [project_root / ".env", project_root / "server" / ".env"]:
    if env_path.exists():
        load_dotenv(env_path, override=True)
        print(f"Loaded {env_path}")

import requests

url = "https://health.api.nvidia.com/v1/biology/deepmind/alphafold2"

# Required: sequence (your payload was missing this)
TEST_SEQUENCE = "MVLSEGEWQLVLHVWAKVEADVAGHGQDILIRLFKSHPETLEKFDRFKHLKTEAEMKASEDLKKHGVTVLTALGAILKKKGHHEAELKPLAQSHATKHKI"

# Payload - add "sequence" and use your params. Simpler: algorithm="mmseqs2", databases=["small_bfd"]
payload = {
    "sequence": TEST_SEQUENCE,
    "algorithm": "jackhmmer",
    "databases": ["uniref90", "mgnify", "small_bfd"],
    "e_value": 0.0001,
    "iterations": 1,
    "relax_prediction": True,
    "structure_model_preset": "monomer",
    "structure_models_to_relax": "all",
    "num_predictions_per_model": 1,
    "template_searcher": "hhsearch",
}

# Required: Authorization header (your script was missing this)
api_key = (os.getenv("NVCF_RUN_KEY") or "").strip()
if not api_key:
    print("ERROR: NVCF_RUN_KEY not set. Add it to server/.env or set env var.")
    sys.exit(1)

headers = {
    "accept": "application/json",
    "content-type": "application/json",
    "Authorization": f"Bearer {api_key}",
    "NVCF-POLL-SECONDS": "10",  # Request 202 + req_id for polling (avoid long-poll)
}

print("Sending request to NVIDIA AlphaFold API...")
print(f"URL: {url}")
print(f"Sequence length: {len(TEST_SEQUENCE)}")
print(f"Auth: Bearer {api_key[:20]}...")

# Initial POST typically returns 202 quickly; use 120s timeout
response = requests.post(url, json=payload, headers=headers, timeout=120)

print(f"\nStatus: {response.status_code}")
print(f"Headers: {dict(response.headers)}")
print(f"\nResponse:\n{response.text[:2000] if response.text else '(empty)'}")

req_id = response.headers.get("nvcf-reqid") or response.headers.get("Nvcf-Reqid")
if req_id:
    status_url = f"https://health.api.nvidia.com/v1/status/{req_id}"
    print(f"\n--- Polling status: {status_url}")
    poll_headers = {"Authorization": f"Bearer {api_key}", "accept": "application/json", "NVCF-POLL-SECONDS": "10"}
    poll_resp = requests.get(status_url, headers=poll_headers, timeout=120)
    print(f"Poll Status: {poll_resp.status_code}")
    print(f"Poll Response: {poll_resp.text[:500] if poll_resp.text else '(empty)'}")
