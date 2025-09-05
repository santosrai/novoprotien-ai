# RFdiffusion API Logging Guide

## Overview

The RFdiffusion client has been enhanced with comprehensive logging to capture all API requests and responses sent to the NVIDIA API. This allows you to analyze exactly what data is being sent and received, helping with debugging and optimization.

## What Gets Logged

### 1. API Request Parameters
- Design mode (unconditional, motif_scaffolding, partial_diffusion)
- Contigs specification
- Hotspot residues
- Diffusion steps
- PDB content length and preview
- Parameter types and values

### 2. NVIDIA API Payload
- Complete API endpoint URL
- Request headers (including authorization)
- Full JSON payload being sent
- Payload size in bytes
- PDB content size in characters

### 3. API Response
- HTTP status codes
- Response headers
- Complete response body
- Parsed JSON response
- Error messages and details

### 4. PDB Processing
- Input PDB line count
- Output ATOM line count
- Processing approach (following official NVIDIA example)
- File saving operations

### 5. Job Lifecycle
- Job initialization
- Client setup
- API submission
- Result processing
- File operations
- Error handling with full tracebacks

## Log Files

### Primary Log File
- **Location**: `logs/rfdiffusion_api.log`
- **Content**: All API-related operations
- **Format**: Timestamped entries with detailed information

### Server Logs
- **Location**: Standard server logs
- **Content**: Job lifecycle and error information
- **Format**: Standard logging format

## How to Analyze the Logs

### 1. Find API Requests
Search for sections marked with:
```
=== RFdiffusion API Request Parameters ===
=== NVIDIA API Payload ===
=== NVIDIA API Response ===
```

### 2. Examine Payload Data
Look for the payload section to see exactly what's sent:
```json
{
  "pdb": "ATOM      1  N   ALA A   1...",
  "contigs": "50-150",
  "hotspot_res": [],
  "diffusion_steps": 15
}
```

### 3. Check Response Status
Look for response sections to see:
- HTTP status codes
- Error messages
- Response data structure

### 4. Analyze PDB Processing
Find PDB processing logs:
```
PDB processing: Input 1000 lines, output 400 ATOM lines (max: 400)
```

## Example Log Analysis

### Successful Request
```
2024-01-15 10:30:15 - rfdiffusion_client.api - INFO - === NVIDIA API Payload ===
2024-01-15 10:30:15 - rfdiffusion_client.api - INFO - API Endpoint: https://health.api.nvidia.com/v1/biology/ipd/rfdiffusion/generate
2024-01-15 10:30:15 - rfdiffusion_client.api - INFO - Payload Size: 15420 bytes
2024-01-15 10:30:15 - rfdiffusion_client.api - INFO - === NVIDIA API Response ===
2024-01-15 10:30:15 - rfdiffusion_client.api - INFO - Status Code: 200
```

### Failed Request
```
2024-01-15 10:30:15 - rfdiffusion_client.api - ERROR - API request failed with status 422: Invalid shape in axis 0: 0
2024-01-15 10:30:15 - rfdiffusion_client.api - ERROR - NVIDIA API error: Invalid input data shape - check PDB content and parameters
```

## Testing the Logging

Run the test script to verify logging is working:
```bash
cd server
python test_rfdiffusion_logging.py
```

This will:
1. Initialize the client
2. Test PDB processing
3. Validate parameters
4. Create sample log entries
5. Show where log files are stored

## Troubleshooting

### No Logs Generated
1. Check if `logs/` directory exists
2. Verify logging level is set to DEBUG or INFO
3. Ensure the client is properly initialized

### Incomplete Logs
1. Check file permissions for log directory
2. Verify disk space
3. Check for logging configuration conflicts

### Performance Impact
The logging adds minimal overhead:
- File I/O only when logging
- JSON serialization for payload logging
- No impact on API request timing

## Best Practices

1. **Monitor Log Size**: Logs can grow large with frequent API calls
2. **Rotate Logs**: Consider log rotation for production use
3. **Filter Logs**: Use grep to find specific information:
   ```bash
   grep "=== NVIDIA API Payload ===" logs/rfdiffusion_api.log
   grep "Status Code: 422" logs/rfdiffusion_api.log
   ```

4. **Archive Logs**: Keep historical logs for trend analysis

## Security Notes

⚠️ **Important**: The logs contain sensitive information:
- API keys in headers (consider masking in production)
- PDB content (may contain proprietary structures)
- Request/response data (may contain sensitive parameters)

For production use, consider:
- Logging only non-sensitive fields
- Implementing log encryption
- Setting appropriate file permissions
- Regular log cleanup

## Integration with Monitoring

The detailed logs can be integrated with:
- Log aggregation systems (ELK stack, Splunk)
- Application performance monitoring (APM)
- Error tracking systems
- Custom dashboards for API usage analysis
