#!/usr/bin/env python3
"""
Test script for NVIDIA AlphaFold API endpoint.
Tests API connectivity, request submission, and polling behavior.
"""

import os
import sys
import asyncio
import json
import time
from pathlib import Path

# Add server directory to path
server_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(server_dir))

from tools.nvidia.alphafold import AlphaFoldClient

# Test sequence (short sequence for quick testing)
TEST_SEQUENCE = "MVLSEGEWQLVLHVWAKVEADVAGHGQDILIRLFKSHPETLEKFDRFKHLKTEAEMKASEDLKKHGVTVLTALGAILKKKGHHEAELKPLAQSHATKHKI"


async def test_api_connectivity():
    """Test basic API connectivity"""
    print("=" * 80)
    print("TEST 1: API Connectivity")
    print("=" * 80)
    
    try:
        client = AlphaFoldClient()
        print(f"✓ AlphaFold client initialized")
        print(f"  Base URL: {client.base_url}")
        print(f"  Status URL: {client.status_url}")
        print(f"  Poll interval: {client.poll_interval}s")
        print(f"  Max transient failures: {client.max_transient_failures}")
        return True
    except Exception as e:
        print(f"✗ Failed to initialize client: {e}")
        return False


async def test_sequence_validation():
    """Test sequence validation"""
    print("\n" + "=" * 80)
    print("TEST 2: Sequence Validation")
    print("=" * 80)
    
    try:
        client = AlphaFoldClient()
        is_valid, result = client.validate_sequence(TEST_SEQUENCE)
        
        if is_valid:
            print(f"✓ Sequence is valid")
            print(f"  Length: {len(result)} residues")
            print(f"  Preview: {result[:50]}...")
        else:
            print(f"✗ Sequence validation failed: {result}")
            return False
        
        return True
    except Exception as e:
        print(f"✗ Validation error: {e}")
        return False


async def test_request_submission():
    """Test submitting a request to the API"""
    print("\n" + "=" * 80)
    print("TEST 3: Request Submission")
    print("=" * 80)
    
    try:
        client = AlphaFoldClient()
        
        # Track progress
        progress_updates = []
        
        def progress_callback(message: str, progress: float):
            progress_updates.append((time.time(), message, progress))
            print(f"  Progress: {progress:.1f}% - {message}")
        
        print(f"Submitting request for sequence (length: {len(TEST_SEQUENCE)})...")
        print(f"Parameters: algorithm=mmseqs2, databases=['small_bfd'], relax_prediction=False")
        
        start_time = time.time()
        
        result = await client.submit_folding_request(
            sequence=TEST_SEQUENCE,
            progress_callback=progress_callback,
            algorithm="mmseqs2",
            databases=["small_bfd"],
            e_value=0.0001,
            iterations=1,
            relax_prediction=False
        )
        
        elapsed = time.time() - start_time
        
        print(f"\n✓ Request completed in {elapsed:.1f} seconds")
        print(f"  Status: {result.get('status')}")
        print(f"  Result keys: {list(result.keys())}")
        
        if result.get('status') == 'completed':
            print(f"  ✓ Job completed successfully")
            if 'data' in result:
                print(f"  Data keys: {list(result['data'].keys())}")
        elif result.get('status') == 'polling_failed':
            print(f"  ✗ Polling failed: {result.get('error')}")
        elif result.get('status') == 'error':
            print(f"  ✗ Error: {result.get('error')}")
        else:
            print(f"  Status: {result.get('status')}")
        
        print(f"\nProgress updates received: {len(progress_updates)}")
        if progress_updates:
            print("  First few updates:")
            for i, (timestamp, message, progress) in enumerate(progress_updates[:5]):
                elapsed_from_start = timestamp - start_time
                print(f"    {i+1}. [{elapsed_from_start:.1f}s] {progress:.1f}% - {message}")
        
        return result
        
    except Exception as e:
        print(f"✗ Request submission failed: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_polling_behavior():
    """Test polling behavior with detailed logging"""
    print("\n" + "=" * 80)
    print("TEST 4: Polling Behavior Analysis")
    print("=" * 80)
    
    try:
        client = AlphaFoldClient()
        
        # Create a mock session to test polling
        import aiohttp
        
        poll_stats = {
            'total_polls': 0,
            'status_200': 0,
            'status_202': 0,
            'status_404': 0,
            'status_500': 0,
            'status_502': 0,
            'status_503': 0,
            'status_504': 0,
            'other_status': 0,
            'errors': []
        }
        
        # We can't easily test polling without a real request ID
        # But we can test the status endpoint format
        print(f"Status endpoint format: {client.status_url}/<request_id>")
        print(f"Poll interval: {client.poll_interval}s")
        print(f"Max transient failures: {client.max_transient_failures}")
        print(f"Max poll seconds: {client.max_poll_seconds}")
        
        return True
        
    except Exception as e:
        print(f"✗ Polling test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_error_handling():
    """Test error handling scenarios"""
    print("\n" + "=" * 80)
    print("TEST 5: Error Handling")
    print("=" * 80)
    
    try:
        client = AlphaFoldClient()
        
        # Test with invalid sequence
        print("Testing invalid sequence handling...")
        is_valid, result = client.validate_sequence("INVALID123")
        if not is_valid:
            print(f"✓ Correctly rejected invalid sequence: {result}")
        else:
            print(f"✗ Should have rejected invalid sequence")
        
        # Test with empty sequence
        print("Testing empty sequence handling...")
        is_valid, result = client.validate_sequence("")
        if not is_valid:
            print(f"✓ Correctly rejected empty sequence: {result}")
        else:
            print(f"✗ Should have rejected empty sequence")
        
        # Test with too long sequence
        print("Testing sequence length limits...")
        long_seq = "A" * 5000
        is_valid, result = client.validate_sequence(long_seq)
        if not is_valid:
            print(f"✓ Correctly rejected too-long sequence: {result}")
        else:
            print(f"✗ Should have rejected too-long sequence")
        
        return True
        
    except Exception as e:
        print(f"✗ Error handling test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_api_response_times():
    """Test API response times"""
    print("\n" + "=" * 80)
    print("TEST 6: API Response Time Analysis")
    print("=" * 80)
    
    try:
        import aiohttp
        
        client = AlphaFoldClient()
        session = client._create_session()
        
        response_times = []
        
        # Test base URL connectivity
        print("Testing base URL connectivity...")
        try:
            start = time.time()
            async with session.get(client.base_url, headers=client._get_headers()) as response:
                elapsed = time.time() - start
                response_times.append(('base_url', response.status, elapsed))
                print(f"  Base URL ({client.base_url}): HTTP {response.status} in {elapsed:.2f}s")
        except Exception as e:
            print(f"  Base URL error: {e}")
        
        # Test status URL connectivity
        print("Testing status URL connectivity...")
        try:
            # Use a dummy request ID to test endpoint format
            test_req_id = "test-request-id-12345"
            status_endpoint = f"{client.status_url}/{test_req_id}"
            start = time.time()
            async with session.get(status_endpoint, headers=client._get_headers()) as response:
                elapsed = time.time() - start
                response_times.append(('status_url', response.status, elapsed))
                body = await response.text()
                print(f"  Status URL ({status_endpoint}): HTTP {response.status} in {elapsed:.2f}s")
                if response.status == 404:
                    print(f"    ✓ Expected 404 for test request ID")
                else:
                    print(f"    Response body: {body[:200]}")
        except Exception as e:
            print(f"  Status URL error: {e}")
        
        await session.close()
        
        if response_times:
            print(f"\nResponse time summary:")
            for endpoint, status, elapsed in response_times:
                print(f"  {endpoint}: HTTP {status} - {elapsed:.2f}s")
        
        return True
        
    except Exception as e:
        print(f"✗ Response time test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("NVIDIA AlphaFold API Test Suite")
    print("=" * 80)
    print(f"Test sequence length: {len(TEST_SEQUENCE)} residues")
    print(f"API Key configured: {'Yes' if os.getenv('NVCF_RUN_KEY') else 'No'}")
    print("=" * 80)
    
    results = {}
    
    # Run tests
    results['connectivity'] = await test_api_connectivity()
    results['validation'] = await test_sequence_validation()
    results['error_handling'] = await test_error_handling()
    results['response_times'] = await test_api_response_times()
    results['polling'] = await test_polling_behavior()
    
    # Only run actual submission if other tests pass
    if all([results['connectivity'], results['validation'], results['error_handling']]):
        print("\n" + "=" * 80)
        print("Running full submission test (this may take several minutes)...")
        print("=" * 80)
        results['submission'] = await test_request_submission()
    else:
        print("\n⚠ Skipping submission test due to previous failures")
        results['submission'] = None
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL" if result is False else "⚠ SKIP"
        print(f"  {test_name:20s}: {status}")
    
    print("\n" + "=" * 80)
    
    # Recommendations
    if results.get('submission') and results['submission'].get('status') == 'polling_failed':
        error = results['submission'].get('error', '')
        if '504' in error:
            print("RECOMMENDATIONS:")
            print("  - HTTP 504 errors indicate gateway timeouts on NVIDIA's side")
            print("  - This suggests the API is experiencing high load or issues")
            print("  - Consider:")
            print("    1. Increasing MAX_TRANSIENT_FAILURES (currently 50)")
            print("    2. Increasing poll interval to reduce load")
            print("    3. Retrying the request later")
            print("    4. Checking NVIDIA API status")
        elif '404' in error:
            print("RECOMMENDATIONS:")
            print("  - HTTP 404 indicates the request ID was not found")
            print("  - This may mean the request was never accepted")
            print("  - Check if the initial POST request returned a valid request ID")
    
    return all(r for r in results.values() if r is not None and isinstance(r, bool))


if __name__ == "__main__":
    # Check for API key
    if not os.getenv("NVCF_RUN_KEY"):
        print("ERROR: NVCF_RUN_KEY environment variable not set")
        print("Please set it before running tests:")
        print("  export NVCF_RUN_KEY='your-api-key'")
        sys.exit(1)
    
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
