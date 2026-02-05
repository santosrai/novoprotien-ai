# Test Script Comparison: Reference vs Implementation

## Overview
This document compares the reference Python test script with our implementation (`test_api_direct.py` and `test_nvidia_api_simple.py`).

## Reference Script Structure

The reference script (provided by user) follows this pattern:

```python
# 1. Make POST request with headers and payload
response = requests.post(url, headers=headers, json=data)

# 2. Handle response codes:
if response.status_code == 200:
    # Immediate completion - save result
elif response.status_code == 202:
    # Request accepted - poll status endpoint
    req_id = response.headers.get("nvcf-reqid")
    while True:
        status_response = requests.get(f"{status_url}/{req_id}", headers=headers)
        if status_response.status_code != 202:
            # Done - save result
            break
else:
    # Unexpected status
```

## Key Parameters (Reference Script)

- **URL**: `https://health.api.nvidia.com/v1/biology/deepmind/alphafold2`
- **Status URL**: `https://health.api.nvidia.com/v1/status`
- **Headers**:
  - `content-type: application/json`
  - `Authorization: Bearer $NVIDIA_API_KEY`
  - `NVCF-POLL-SECONDS: 300` (5 minutes)
- **Payload**:
  - `sequence`: 160-residue test sequence
  - `algorithm: "mmseqs2"`
  - `e_value: 0.0001`
  - `iterations: 1`
  - `databases: ["uniref90", "small_bfd"]`
  - `relax_prediction: False`
  - `skip_template_search: True`

## Our Implementation: `test_api_direct.py`

### Similarities
✅ Uses `requests` library (synchronous, matching reference)  
✅ Same URL endpoints  
✅ Same headers structure  
✅ Same payload parameters  
✅ Handles 200 (immediate completion)  
✅ Handles 202 (accepted, poll status)  
✅ Polls status endpoint with same pattern  

### Enhancements
🆕 **5xx Error Handling**: Handles 500/502/503/504 responses that may include `nvcf-reqid`  
🆕 **Better Logging**: More detailed progress and error messages  
🆕 **Timeout Handling**: Handles request timeouts gracefully  
🆕 **Keyboard Interrupt**: Clean exit on Ctrl+C with request ID for manual checking  
🆕 **Status Header Checking**: Validates `nvcf-status` header before polling  
🆕 **Option Flags**: `--no-skip-template` to test without `skip_template_search`  

### Differences

| Aspect | Reference Script | Our Implementation |
|--------|------------------|-------------------|
| **5xx Handling** | Exits with error | Attempts to poll if `nvcf-reqid` present |
| **Poll Interval** | Hardcoded 300s wait | Configurable via `POLL_INTERVAL` env var |
| **Error Messages** | Basic | Detailed with recommendations |
| **Timeout** | None | 310s timeout on status requests |
| **Transient Errors** | Not handled | Retries on 5xx during polling |

## Our Implementation: `test_nvidia_api_simple.py`

### Differences from Reference
- **Async**: Uses `aiohttp` and `asyncio` (async/await pattern)
- **Client Wrapper**: Uses `AlphaFoldClient` class instead of direct `requests`
- **Progress Callbacks**: Supports progress callbacks during polling
- **More Robust**: Includes retry logic, exponential backoff, error classification

### When to Use Which

- **`test_api_direct.py`**: When you want to match the reference script exactly (synchronous, simple)
- **`test_nvidia_api_simple.py`**: When you want to test the actual client implementation used by the app (async, more features)

## API Behavior Observations

### Common Response Patterns

1. **200 OK**: Immediate completion (rare for long sequences)
   - Response body contains PDB structure
   - No polling needed

2. **202 Accepted**: Request queued/processing
   - `nvcf-reqid` header contains request ID
   - Must poll status endpoint
   - Status endpoint returns 202 while processing, 200 when complete

3. **500/502/503/504**: Transient errors
   - May include `nvcf-reqid` if request was accepted
   - `nvcf-status` header indicates job state:
     - `"queued"` or `"running"`: Job accepted, poll status
     - `"errored"`: Job failed, don't poll
   - Reference script doesn't handle this case

### Known Issues

⚠️ **`skip_template_search` Parameter**: 
- May not be supported by the API
- Can cause 500 errors with `nvcf-status: errored`
- Our handler filters it out (not in `supported_params`)
- Test with `--no-skip-template` flag to verify

⚠️ **500 Errors**:
- API sometimes returns 500 even with valid requests
- If `nvcf-status: errored`, the job was not accepted
- If `nvcf-status: queued/running`, the job may still process (poll status)

## Recommendations

1. **For Testing**: Use `test_api_direct.py` to match reference behavior exactly
2. **For Debugging**: Use `test_nvidia_api_simple.py` to test actual app client
3. **For Production**: Our async client (`AlphaFoldClient`) handles all edge cases
4. **Parameter Validation**: Remove `skip_template_search` if causing 500 errors

## Testing Commands

```bash
# Test with reference script parameters (including skip_template_search)
python3 server/tools/nvidia/test_api_direct.py

# Test without skip_template_search
python3 server/tools/nvidia/test_api_direct.py --no-skip-template

# Test with async client (more robust)
python3 server/tools/nvidia/test_nvidia_api_simple.py

# Test with shorter sequence (faster)
python3 server/tools/nvidia/test_nvidia_api_simple.py --short
```
