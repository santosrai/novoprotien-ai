#!/usr/bin/env python3
"""
OpenFold2 API example - corrected from official NVIDIA example.
Usage:
  (1) export NVCF_RUN_KEY=<your key>   # or NVIDIA_API_KEY
  (2) python tests/openfold2_example.py
  (3) View output in tests/output1.json
"""
import os
from pathlib import Path

# Load .env from server/ if available
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / "server" / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

import requests
from pathlib import Path

# ----------------------------
# parameters
# ----------------------------
url = os.getenv(
    "OPENFOLD2_URL",
    "https://health.api.nvidia.com/v1/biology/openfold/openfold2/predict-structure-from-msa-and-template",
)
output_file = Path(__file__).parent / "output1.json"
selected_models = [1, 2]
sequence = (
    "GGSKENEISHHAKEIERLQKEIERHKQSIKKLKQSEQSNPPPNPEG"
    "TRQARRNRRRRWRERQRQKENEISHHAKEIERLQKEIERHKQSIKKLKQSEC"
)

small_bfd_alignment_in_a3m = """>BQXYMDHSRWGGVPIWVK
GGSKENEISHHAKEIERLQKEIERHKQSIKKLKQSEQSNPPPNPEGTRQARRNRRRRWRERQRQKENEISHHAKEIERLQKEIERHKQSIKKLKQSEC
>A0A076V4A1_9HIV1
------------------------------------QSNPPPNHEGTRQARRNRRRRWRERQRQ----------------------------------
"""

# FIX: Use os.getenv() - "$NVIDIA_API_KEY" in the original is a literal string!
api_key = os.getenv("NVCF_RUN_KEY") or os.getenv("NVIDIA_API_KEY")
if not api_key:
    print("ERROR: Set NVCF_RUN_KEY or NVIDIA_API_KEY")
    exit(1)

data = {
    "sequence": sequence,
    "alignments": {
        "small_bfd": {
            "a3m": {
                "alignment": small_bfd_alignment_in_a3m,
                "format": "a3m",
            }
        },
    },
    "selected_models": selected_models,
    "relax_prediction": False,
}

headers = {
    "content-type": "application/json",
    "Authorization": f"Bearer {api_key}",
    "NVCF-POLL-SECONDS": "300",
}

print("Making request...")
response = requests.post(url, headers=headers, json=data, timeout=600)

if response.status_code == 200:
    output_file.write_text(response.text)
    print(f"Response saved to {output_file}")
    # Show top-level keys for debugging
    try:
        import json
        d = response.json()
        print(f"Response keys: {list(d.keys())}")
    except Exception:
        pass
else:
    print(f"HTTP {response.status_code}: {response.text[:500]}")
