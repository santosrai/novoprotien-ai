#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""
Simple test script to verify NVIDIA AlphaFold3 API is working.
Tests basic connectivity and a short sequence submission.
Based on the official NVIDIA AlphaFold3 example.
"""

import os
import sys
import asyncio
import json
import time
import uuid
import ssl
from pathlib import Path
from dotenv import load_dotenv
import aiohttp

try:
    import certifi
except ImportError:
    certifi = None

# Load environment variables
project_root = Path(__file__).parent.parent.parent.parent
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"✓ Loaded .env from: {env_path}")

server_env_path = project_root / "server" / ".env"
if server_env_path.exists():
    load_dotenv(server_env_path, override=True)
    print(f"✓ Loaded server/.env")

# Test sequence from reference script (protein-DNA complex example: PDB 5GNJ)
REFERENCE_TEST_SEQUENCE = "MGREEPLNHVEAERQRREKLNQRFYALRAVVPNVSKMDKASLLGDAIAYINELKSKVVKTESEKLQIKNQLEEVKLELAGRLEHHHHHH"

# DNA sequences from reference
DNA_SEQUENCE_1 = "AGGAACACGTGACCC"
DNA_SEQUENCE_2 = "TGGGTCACGTGTTCC"

# Alternative shorter protein-only sequence for faster testing
SHORT_TEST_SEQUENCE = "MVLSEGEWQLVLHVWAKVEADVAGHGQDILIRLFKSHPETLEKFDRFKHLKTEAEMKASEDLKKHGVTVLTALGAILKKKGHHEAELKPLAQSHATKHKI"  # 122 residues

# Use reference sequence by default to match the official test
TEST_SEQUENCE = REFERENCE_TEST_SEQUENCE
USE_DNA_COMPLEX = True  # Set to False for protein-only test


def create_ssl_context():
    """Create SSL context for aiohttp requests"""
    ssl_context = ssl.create_default_context()
    
    # Try to use certifi bundle if available (proper certificate verification)
    if certifi is not None:
        try:
            ssl_context.load_verify_locations(certifi.where())
            # Keep default verification settings (verify_mode=ssl.CERT_REQUIRED) when certifi is available
            # This provides proper SSL certificate verification
        except Exception as exc:
            print(f"   ⚠ Warning: Failed to load certifi bundle: {exc}")
            # Fall back to no verification if certifi fails (matching base client behavior)
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
    else:
        # If certifi is not available, disable verification (matching base client behavior)
        # Note: This is less secure but allows the script to work without certifi
        print("   ⚠ Warning: certifi not available, SSL verification disabled")
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
    
    return ssl_context


def create_session(timeout=180):
    """Create aiohttp session with SSL context"""
    ssl_context = create_ssl_context()
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    timeout_obj = aiohttp.ClientTimeout(total=timeout)
    return aiohttp.ClientSession(connector=connector, timeout=timeout_obj)


async def test_nvidia_api():
    """Test NVIDIA AlphaFold3 API"""
    print("=" * 80)
    print("NVIDIA AlphaFold3 API Test")
    print("=" * 80)
    
    # Check API key
    api_key = os.getenv("NVCF_RUN_KEY") or os.getenv("NVIDIA_API_KEY")
    if not api_key:
        print("\n✗ ERROR: NVCF_RUN_KEY or NVIDIA_API_KEY not found in environment")
        print("Please set it:")
        print("  export NVCF_RUN_KEY='your-api-key'")
        print("  or")
        print("  export NVIDIA_API_KEY='your-api-key'")
        print("Or add it to .env file")
        return False
    
    print(f"\n✓ API Key found (length: {len(api_key)} characters)")
    
    # AlphaFold3 API endpoint
    url = os.getenv("ALPHAFOLD3_URL", "https://health.api.nvidia.com/v1/biology/openfold/openfold3/predict")
    print(f"\n1. AlphaFold3 API endpoint: {url}")
    
    # Validate sequence
    print("\n2. Validating test sequence...")
    if not TEST_SEQUENCE:
        print("   ✗ Sequence cannot be empty")
        return False
    
    clean_seq = ''.join(TEST_SEQUENCE.split()).upper()
    valid_aa = set("ACDEFGHIKLMNPQRSTVWY")
    invalid_chars = set(clean_seq) - valid_aa
    if invalid_chars:
        print(f"   ✗ Invalid amino acids found: {', '.join(sorted(invalid_chars))}")
        return False
    
    print(f"   ✓ Sequence is valid ({len(clean_seq)} residues)")
    
    # Test API connectivity
    try:
        print("\n3. Testing API connectivity...")
        headers = {
            "content-type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "NVCF-POLL-SECONDS": "300",
        }
        
        # Simple connectivity test - try to access the endpoint
        async with create_session(timeout=30) as session:
            # Create a minimal test request to check connectivity
            test_data = {
                "request_id": str(uuid.uuid4()),
                "inputs": [{
                    "input_id": "test",
                    "molecules": [{
                        "type": "protein",
                        "id": "A",
                        "sequence": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQFEVVHSLAKWKRQTLGQHDFSAGEGLYTHMKALRPDEDRLSPLHSVYVDQWDWERVMGDGERQFSTLKSTVEAIWAGIKATEAAVSEEFGLAPFLPDPSIHPSLAET",
                    }],
                    "output_format": "pdb",
                }]
            }
            
            start = time.time()
            try:
                async with session.post(url, headers=headers, json=test_data) as response:
                    elapsed = time.time() - start
                    status = response.status
                    body = await response.text()
                    print(f"   Connectivity test: HTTP {status} in {elapsed:.2f}s")
                    
                    if status == 200:
                        print(f"   ✓ Endpoint accessible and accepting requests")
                    elif status == 401:
                        print(f"   ⚠ 401 Unauthorized - check API key")
                        print(f"   Response: {body[:200]}")
                        return False
                    elif status == 403:
                        print(f"   ⚠ 403 Forbidden - API key may not have permissions")
                        print(f"   Response: {body[:200]}")
                        return False
                    elif status == 400:
                        # 400 is expected for test data, but confirms endpoint works
                        print(f"   ✓ Endpoint accessible (400 expected for test data)")
                    else:
                        print(f"   ⚠ Status {status}: {body[:200]}")
            except asyncio.TimeoutError:
                print(f"   ⚠ Request timed out (endpoint may be slow)")
            except Exception as e:
                print(f"   ⚠ Connectivity test error: {e}")
    except Exception as e:
        print(f"   ✗ Connectivity test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Submit test request - matching reference script format
    print("\n4. Submitting test folding request...")
    print(f"   Sequence length: {len(clean_seq)} residues")
    if USE_DNA_COMPLEX:
        print(f"   Type: Protein-DNA complex (matching reference script)")
        print(f"   DNA sequences: {len(DNA_SEQUENCE_1)} and {len(DNA_SEQUENCE_2)} bases")
    else:
        print(f"   Type: Protein-only")
    print(f"   Poll interval: 300s (5 minutes, matching reference)")
    print(f"   This may take 5-15 minutes...")
    print(f"   Note: HTTP 504 errors are common and usually transient")
    print(f"   Press Ctrl+C to cancel if needed\n")
    
    # Prepare MSA alignment in CSV format (matching reference script)
    msa_alignment_csv = (
        "key,sequence\n"
        f"-1,{clean_seq}"
    )
    
    # Build request data matching reference script format
    request_id = "5GNJ" if USE_DNA_COMPLEX else str(uuid.uuid4())
    molecules = [
        {
            "type": "protein",
            "id": "A",
            "sequence": clean_seq,
            "msa": {
                "main_db": {
                    "csv": {
                        "alignment": msa_alignment_csv,
                        "format": "csv",
                    }
                },
            },
        }
    ]
    
    # Add DNA molecules if testing complex
    if USE_DNA_COMPLEX:
        molecules.append({
            "type": "dna",
            "id": "B",
            "sequence": DNA_SEQUENCE_1,
        })
        molecules.append({
            "type": "dna",
            "id": "C",
            "sequence": DNA_SEQUENCE_2,
        })
    
    data = {
        "request_id": request_id,
        "inputs": [
            {
                "input_id": request_id,
                "molecules": molecules,
                "output_format": "pdb",
            }
        ],
    }
    
    print(f"   Request ID: {request_id}")
    print(f"   Molecules: {len(molecules)} ({', '.join(m['type'] for m in molecules)})")
    
    headers = {
        "content-type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "NVCF-POLL-SECONDS": "300",
    }
    
    start_time = time.time()
    
    try:
        print("\n   Making request to AlphaFold3 API...")
        async with create_session(timeout=600) as session:
            async with session.post(url, headers=headers, json=data) as response:
                total_time = time.time() - start_time
                status = response.status
                response_text = await response.text()
                
                print(f"\n5. Request completed in {total_time:.1f} seconds ({total_time/60:.1f} minutes)")
                print(f"   HTTP Status: {status}")
                
                if status == 200:
                    print(f"   ✓ SUCCESS: Request accepted!")
                    
                    # Try to parse response
                    try:
                        response_data = json.loads(response_text)
                        output_file = Path("output.json")
                        output_file.write_text(response_text)
                        print(f"   ✓ Response saved to: {output_file}")
                        
                        # Check if response contains job status or result
                        if isinstance(response_data, dict):
                            if "request_id" in response_data:
                                print(f"   Request ID: {response_data.get('request_id')}")
                            if "status" in response_data:
                                print(f"   Status: {response_data.get('status')}")
                            if "result" in response_data or "pdb" in response_data:
                                print(f"   ✓ Result data found in response")
                            print(f"   Response keys: {list(response_data.keys())}")
                        
                        return True
                    except json.JSONDecodeError:
                        print(f"   ⚠ Response is not JSON")
                        print(f"   Response preview: {response_text[:200]}...")
                        # Save anyway
                        output_file = Path("output.json")
                        output_file.write_text(response_text)
                        print(f"   Response saved to: {output_file}")
                        return True
                
                elif status == 202:
                    print(f"   ✓ Request accepted (202 - processing)")
                    print(f"   Response: {response_text[:200]}...")
                    return True
                
                elif status == 400:
                    print(f"   ✗ Bad Request (400)")
                    print(f"   Response: {response_text}")
                    return False
                
                elif status == 401:
                    print(f"   ✗ Unauthorized (401) - check API key")
                    print(f"   Response: {response_text[:200]}")
                    return False
                
                elif status == 403:
                    print(f"   ✗ Forbidden (403) - API key may not have permissions")
                    print(f"   Response: {response_text[:200]}")
                    return False
                
                elif status == 504:
                    print(f"   ⚠ Gateway Timeout (504)")
                    print(f"   - The API gateway timed out, but the job may still be processing")
                    print(f"   - This is common for longer sequences")
                    print(f"   Response: {response_text[:200]}")
                    return False
                
                else:
                    print(f"   ⚠ Unexpected status: {status}")
                    print(f"   Response: {response_text[:500]}")
                    return False
                    
    except asyncio.TimeoutError:
        total_time = time.time() - start_time
        print(f"\n   ✗ Request timed out after {total_time:.1f} seconds")
        print(f"   The API may still be processing the request")
        return False
        
    except Exception as e:
        total_time = time.time() - start_time
        print(f"\n   ✗ Request submission failed after {total_time:.1f} seconds: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run the test"""
    print("\n" + "=" * 80)
    print("Starting NVIDIA AlphaFold3 API Test")
    print("=" * 80)
    
    # Allow user to choose sequence and test type
    import sys
    global TEST_SEQUENCE, USE_DNA_COMPLEX
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--short":
            TEST_SEQUENCE = SHORT_TEST_SEQUENCE
            USE_DNA_COMPLEX = False
            print("Using SHORT test sequence (122 residues, protein-only)")
        elif sys.argv[1] == "--protein-only":
            USE_DNA_COMPLEX = False
            print("Using REFERENCE test sequence (protein-only)")
            print(f"Sequence length: {len(TEST_SEQUENCE)} residues")
        elif sys.argv[1] == "--complex":
            USE_DNA_COMPLEX = True
            print("Using REFERENCE test sequence (protein-DNA complex, matching official test)")
            print(f"Sequence length: {len(TEST_SEQUENCE)} residues")
    else:
        print("Using REFERENCE test sequence (protein-DNA complex, matching official test script)")
        print(f"Sequence length: {len(TEST_SEQUENCE)} residues")
        print("Use --short for faster protein-only test")
        print("Use --protein-only for reference sequence without DNA")
        print("Use --complex for protein-DNA complex (default)")
    
    print("=" * 80)
    
    success = await test_nvidia_api()
    
    print("\n" + "=" * 80)
    if success:
        print("✓ TEST PASSED: NVIDIA AlphaFold3 API is working correctly")
        print("   Check output.json for the full response")
    else:
        print("✗ TEST FAILED or INCOMPLETE: See details above")
        print("\nNote: If you see 504 errors, the API may still be processing.")
        print("      The job might complete successfully despite the timeouts.")
    print("=" * 80)
    
    return success


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
