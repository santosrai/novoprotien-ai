# NVIDIA AlphaFold API Test Scripts

## Overview

This directory contains test scripts to diagnose and verify NVIDIA AlphaFold API integration.

## Scripts

### 1. `test_alphafold_api.py`
Comprehensive test suite that validates:
- API connectivity
- Sequence validation
- Request submission
- Polling behavior
- Error handling
- Response times

**Usage:**
```bash
export NVCF_RUN_KEY='your-api-key'
python3 server/tools/nvidia/test_alphafold_api.py
```

### 2. `diagnose_504_issue.py`
Focused diagnostic script for HTTP 504 (Gateway Timeout) issues during polling.

**Usage:**
```bash
export NVCF_RUN_KEY='your-api-key'
python3 server/tools/nvidia/diagnose_504_issue.py
```

This script will:
- Check API configuration
- Test endpoint connectivity
- Analyze 504 error patterns
- Provide recommendations
- Optionally run a test submission

## Understanding HTTP 504 Errors

HTTP 504 (Gateway Timeout) errors during polling indicate:

1. **The NVIDIA API gateway is timing out** - This is typically a transient issue
2. **The job may still be processing** - Despite the timeout, the actual computation might continue
3. **High API load** - The service may be experiencing high demand

### Current Behavior

- **Max transient failures**: 50 (configurable via `MAX_TRANSIENT_FAILURES`)
- **Poll interval**: 10 seconds (configurable via `POLL_INTERVAL`)
- **Max wait time**: 1800 seconds / 30 minutes (configurable via `NIMS_MAX_WAIT_SECONDS`)

### Improvements Made

1. **Smarter 504 handling**:
   - Longer backoff for 504s (up to 60 seconds)
   - Extended failure limit for early-stage 504s (50% more tolerance)
   - Better logging to track 504 patterns

2. **Better error messages**:
   - Clear indication when 504s are occurring
   - Suggestions for configuration adjustments
   - Time-based context in error messages

## Configuration Recommendations

### For Persistent 504 Issues

**Option 1: Increase max transient failures**
```bash
export MAX_TRANSIENT_FAILURES=100
```

**Option 2: Increase poll interval**
```bash
export POLL_INTERVAL=30  # Poll every 30 seconds instead of 10
```

**Option 3: Increase max wait time**
```bash
export NIMS_MAX_WAIT_SECONDS=3600  # Allow up to 1 hour
```

**Option 4: Combine all three**
```bash
export MAX_TRANSIENT_FAILURES=100
export POLL_INTERVAL=30
export NIMS_MAX_WAIT_SECONDS=3600
```

## Interpreting Test Results

### Successful Test
- All connectivity tests pass
- Request submission completes
- Status: `completed`

### 504 Issues Detected
- Multiple 504 errors during polling
- Status: `polling_failed`
- **Action**: See configuration recommendations above

### 404 Issues Detected
- Request ID not found
- Status: `polling_failed`
- **Action**: Check if initial POST request was accepted

### Other Errors
- Check error message for specific issue
- Verify API key is valid
- Check NVIDIA API status: https://status.nvidia.com/

## Troubleshooting

### "NVCF_RUN_KEY not set"
- Set the environment variable: `export NVCF_RUN_KEY='your-key'`
- Or add it to `.env` file in project root

### "Connection refused" or network errors
- Check internet connectivity
- Verify firewall settings
- Check if NVIDIA API is accessible

### "401 Unauthorized"
- Verify API key is correct
- Check if API key has AlphaFold permissions
- Regenerate API key if needed

### Consistent 504 errors
- This indicates NVIDIA API is experiencing issues
- Try again later
- Consider increasing configuration values as recommended above

## Notes

- Test scripts consume API credits when running actual submissions
- Use test sequences for quick validation
- Long sequences will take longer and consume more credits
- Monitor API usage in NVIDIA dashboard
