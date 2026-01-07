#!/usr/bin/env python3
"""
Diagnostic script specifically for HTTP 504 polling issues.
Tests the polling mechanism and provides recommendations.
"""

import os
import sys
import asyncio
import json
import time
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
server_dir = Path(__file__).parent.parent.parent
env_path = server_dir / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"Loaded .env from: {env_path}")

# Add server directory to path
sys.path.insert(0, str(server_dir))

from tools.nvidia.alphafold import AlphaFoldClient

# Short test sequence
TEST_SEQUENCE = "MVLSEGEWQLVLHVWAKVEADVAGHGQDILIRLFKSHPETLEKFDRFKHLKTEAEMKASEDLKKHGVTVLTALGAILKKKGHHEAELKPLAQSHATKHKI"


async def diagnose_polling_issue():
    """Diagnose the 504 polling issue"""
    print("=" * 80)
    print("NVIDIA AlphaFold API - 504 Polling Issue Diagnostic")
    print("=" * 80)
    
    # Check configuration
    print("\n1. Configuration Check:")
    print("-" * 80)
    api_key = os.getenv("NVCF_RUN_KEY")
    if not api_key:
        print("✗ NVCF_RUN_KEY not set")
        return False
    else:
        print(f"✓ NVCF_RUN_KEY configured (length: {len(api_key)})")
    
    try:
        client = AlphaFoldClient()
        print(f"✓ Client initialized")
        print(f"  Base URL: {client.base_url}")
        print(f"  Status URL: {client.status_url}")
        print(f"  Poll interval: {client.poll_interval}s")
        print(f"  Max transient failures: {client.max_transient_failures}")
        print(f"  Max poll seconds: {client.max_poll_seconds}")
    except Exception as e:
        print(f"✗ Failed to initialize client: {e}")
        return False
    
    # Test API connectivity
    print("\n2. API Connectivity Test:")
    print("-" * 80)
    try:
        import aiohttp
        session = client._create_session()
        
        # Test status endpoint format
        test_req_id = "test-12345"
        status_endpoint = f"{client.status_url}/{test_req_id}"
        print(f"Testing status endpoint: {status_endpoint}")
        
        start = time.time()
        try:
            async with session.get(status_endpoint, headers=client._get_headers()) as response:
                elapsed = time.time() - start
                body = await response.text()
                print(f"  Response: HTTP {response.status} in {elapsed:.2f}s")
                print(f"  Headers: {dict(response.headers)}")
                
                if response.status == 404:
                    print("  ✓ Expected 404 for test request ID")
                    print("  ✓ Status endpoint is accessible")
                elif response.status == 401:
                    print("  ⚠ 401 Unauthorized - check API key")
                elif response.status == 403:
                    print("  ⚠ 403 Forbidden - API key may not have permissions")
                else:
                    print(f"  ⚠ Unexpected status: {response.status}")
                    print(f"  Body: {body[:200]}")
        except Exception as e:
            print(f"  ✗ Connection error: {e}")
        
        await session.close()
    except Exception as e:
        print(f"✗ Connectivity test failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Analyze the 504 issue
    print("\n3. 504 Error Analysis:")
    print("-" * 80)
    print("HTTP 504 (Gateway Timeout) indicates:")
    print("  - The NVIDIA API gateway is timing out")
    print("  - This is typically a transient issue on NVIDIA's side")
    print("  - The request may still be processing despite the timeout")
    print("\nCurrent behavior:")
    print(f"  - Max transient failures: {client.max_transient_failures}")
    print(f"  - After {client.max_transient_failures} consecutive 504s, polling stops")
    print(f"  - This happened after ~861 seconds (~14 minutes)")
    
    # Recommendations
    print("\n4. Recommendations:")
    print("-" * 80)
    print("Option 1: Increase max transient failures")
    print("  Set environment variable: MAX_TRANSIENT_FAILURES=100")
    print("  This allows more 504 errors before giving up")
    print()
    print("Option 2: Increase poll interval")
    print("  Set environment variable: POLL_INTERVAL=30")
    print("  Reduces API load and may help with timeouts")
    print()
    print("Option 3: Increase max wait time")
    print("  Set environment variable: NIMS_MAX_WAIT_SECONDS=3600")
    print("  Allows jobs to run longer (up to 1 hour)")
    print()
    print("Option 4: Check NVIDIA API status")
    print("  Visit: https://status.nvidia.com/")
    print("  The API may be experiencing issues")
    
    # Test with actual submission (optional)
    print("\n5. Optional: Test Actual Submission")
    print("-" * 80)
    response = input("Run actual API submission test? (y/n): ").strip().lower()
    
    if response == 'y':
        print("\nSubmitting test request...")
        print("(This may take several minutes and will consume API credits)")
        
        progress_updates = []
        start_time = time.time()
        
        def progress_callback(message: str, progress: float):
            elapsed = time.time() - start_time
            progress_updates.append((elapsed, message, progress))
            print(f"  [{elapsed:6.1f}s] {progress:5.1f}% - {message}")
        
        try:
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
            
            if result.get('status') == 'polling_failed':
                error = result.get('error', '')
                print(f"  Error: {error}")
                
                # Count 504s in progress updates
                status_504_count = sum(1 for _, msg, _ in progress_updates if '504' in msg)
                print(f"\n  Progress updates with 504: {status_504_count}")
                print(f"  Total progress updates: {len(progress_updates)}")
                
                if '504' in error:
                    print("\n  ⚠ Confirmed 504 issue - see recommendations above")
            
            return result.get('status') == 'completed'
            
        except Exception as e:
            print(f"✗ Submission test failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    else:
        print("Skipping submission test")
        return True


async def main():
    """Run diagnostic"""
    success = await diagnose_polling_issue()
    
    print("\n" + "=" * 80)
    if success:
        print("Diagnostic completed successfully")
    else:
        print("Diagnostic completed with issues - see recommendations above")
    print("=" * 80)
    
    return success


if __name__ == "__main__":
    if not os.getenv("NVCF_RUN_KEY"):
        print("ERROR: NVCF_RUN_KEY environment variable not set")
        print("Please set it before running:")
        print("  export NVCF_RUN_KEY='your-api-key'")
        print("Or ensure it's in .env file")
        sys.exit(1)
    
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
