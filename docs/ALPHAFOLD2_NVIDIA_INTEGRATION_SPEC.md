# AlphaFold2 NVIDIA API Integration Specification

## 1. Overview

This specification defines the integration of AlphaFold2 protein structure prediction using the NVIDIA Health API, following the same architectural patterns as the existing RFdiffusion integration. The goal is to create a consistent, maintainable, and scalable implementation that leverages shared infrastructure while accommodating AlphaFold2's unique polling-based API pattern.

### 1.1 Objectives

- Integrate AlphaFold2 via NVIDIA Health API (`https://health.api.nvidia.com/v1/biology/deepmind/alphafold2`)
- Follow RFdiffusion integration patterns for consistency
- Implement robust polling mechanism for long-running jobs (30-60 minutes)
- Provide real-time progress updates via WebSocket/SSE
- Support comprehensive error handling and recovery
- Enable full monitoring and observability

### 1.2 Key Requirements

- **API Compliance**: Strictly follow NVIDIA API documentation (sequence ≤4096 chars, relax_prediction boolean)
- **Architecture**: Base class pattern with inheritance for shared functionality
- **Error Recovery**: Hybrid approach - in-memory for active jobs, database for history/recovery
- **Progress Updates**: Real-time via WebSocket/SSE (not polling-based)
- **Sequence Validation**: Validate against 4096 character limit (NVIDIA specification)
- **Result Storage**: Separate `server/alphafold_results/` directory with user-scoped storage
- **Session Integration**: Auto-associate jobs with chat sessions
- **Monitoring**: Full monitoring with logging, metrics, admin dashboard, alerting

---

## 2. Architecture

### 2.1 Client Architecture Pattern

**Base Class with Inheritance**

Create a base `NVIDIAHealthClient` class that both `RFdiffusionClient` and `AlphaFoldClient` inherit from:

```
server/tools/nvidia/
├── base.py                    # NVIDIAHealthClient base class
├── rfdiffusion.py             # RFdiffusionClient (inherits from base)
├── alphafold.py               # AlphaFoldClient (inherits from base, adds polling)
└── proteinmpnn.py            # ProteinMPNNClient (inherits from base)
```

**Base Class Responsibilities:**
- API key management (`NVCF_RUN_KEY`)
- Common HTTP client setup (aiohttp, SSL context)
- Shared error handling patterns
- Common logging infrastructure
- Request/response utilities

**AlphaFoldClient Specific:**
- Polling logic for 202 Accepted responses
- Status endpoint polling (`/v1/status/{req_id}`)
- Progress estimation and callbacks
- Timeout and retry handling for long-running jobs

### 2.2 Handler Architecture

**Handler Pattern (mirrors RFdiffusion):**

```
server/agents/handlers/
├── alphafold.py              # AlphaFoldHandler (refactored)
└── rfdiffusion.py            # RFdiffusionHandler (existing)
```

**AlphaFoldHandler Responsibilities:**
- Natural language request parsing
- Sequence extraction (PDB IDs, chains, residue ranges, direct input)
- Parameter validation and normalization
- Job submission and status tracking
- Result processing and file storage
- Session association
- Error handling and user-friendly messages

### 2.3 Polling Strategy

**Polling Logic Location: Client Layer**

- Keep polling logic in `AlphaFoldClient` (not handler)
- Handler calls client method, client handles all polling complexity
- Client provides progress callbacks for real-time updates
- Handler receives final result or error

**Polling Flow:**
1. POST to `/v1/biology/deepmind/alphafold2` → 202 Accepted + `nvcf-reqid`
2. Poll `GET /v1/status/{req_id}` at configured interval
3. Continue until 200 (completed) or error/timeout
4. Return result to handler

**Polling Configuration:**
- Default interval: 10 seconds (configurable via `POLL_INTERVAL`)
- Max polls: Unlimited by default (configurable via `NIMS_MAX_POLLS`)
- Max wait time: 1800 seconds (30 minutes, configurable via `NIMS_MAX_WAIT_SECONDS`)
- Transient error handling: Retry on 502/503/504 with backoff

---

## 3. API Integration

### 3.1 Request Format

**API Parameters (Based on NVIDIA API Documentation):**

**Required:**
- `sequence` (string, required, ≤4096 characters)

**Optional Parameters:**
- `algorithm` (string): MSA search algorithm - `"mmseqs2"` or `"jackhmmer"` (default: `"mmseqs2"`)
- `databases` (array of strings): MSA databases to search - `["uniref90", "mgnify", "small_bfd", "bfd", "uniclust30"]` (default: `["small_bfd"]`)
- `e_value` (float): E-value threshold for MSA search (default: `0.0001`)
- `iterations` (integer): Number of MSA search iterations, 1-3 (default: `1`)
- `relax_prediction` (boolean): Whether to relax the predicted structure (default: `true`)
- `structure_model_preset` (string): Model preset - `"monomer"` or `"multimer"` (default: `"monomer"`)
- `structure_models_to_relax` (string): Which models to relax - `"all"`, `"best"`, or `"none"` (default: `"all"`)
- `num_predictions_per_model` (integer): Number of predictions per model (default: `1`)
- `template_searcher` (string): Template search algorithm - `"hhsearch"` or other (default: `"hhsearch"`)

**Request Payload Example:**
```json
{
  "sequence": "MVLSEGEWQLVLHVWAKVEADVAGHGQDILIRLFKSHPETLEKFDRFKHLKTEAEMKASEDLK",
  "algorithm": "jackhmmer",
  "databases": ["uniref90", "mgnify", "small_bfd"],
  "e_value": 0.0001,
  "iterations": 1,
  "relax_prediction": true,
  "structure_model_preset": "monomer",
  "structure_models_to_relax": "all",
  "num_predictions_per_model": 1,
  "template_searcher": "hhsearch"
}
```

**Minimal Request (using defaults):**
```json
{
  "sequence": "MVLSEGEWQLVLHVWAKVEADVAGHGQDILIRLFKSHPETLEKFDRFKHLKTEAEMKASEDLK"
}
```

**Parameter Validation:**
- Validate `algorithm` is one of allowed values
- Validate `databases` contains only valid database names
- Validate `e_value` is positive float
- Validate `iterations` is integer between 1-3
- Validate `structure_model_preset` is "monomer" or "multimer"
- Validate `structure_models_to_relax` is "all", "best", or "none"
- Validate `num_predictions_per_model` is positive integer
- Validate `template_searcher` is valid algorithm name

### 3.2 Response Format

**Flexible Response Parsing:**

The API documentation doesn't specify exact response structure. Implement flexible parsing:

1. Try `result_data["pdb"]` (primary location)
2. Try `result_data["structure"]` (alternative)
3. Try `result_data["prediction"]["pdb"]` (nested)
4. Try `result_data["result"]` (recursive search)

**Response Handling:**
- 200: Immediate completion (rare)
- 202: Accepted, requires polling (common)
- 4xx: Client error (validation, auth, etc.)
- 5xx: Server error (retry with backoff)

### 3.3 Sequence Validation

**Validation Rules:**
- Maximum length: 4096 characters (NVIDIA limit)
- Minimum length: 20 residues (biological minimum)
- Valid amino acids: ACDEFGHIKLMNPQRSTVWY (standard 20)
- Normalization: Remove whitespace, convert to uppercase
- Non-standard amino acids: Reject (don't convert or pass through)

**Validation Function:**
```python
def validate_sequence(sequence: str) -> Tuple[bool, str]:
    """
    Returns: (is_valid, cleaned_sequence_or_error_message)
    """
```

### 3.4 Parameter Defaults & Configuration

**Default Parameter Values:**
```python
DEFAULT_PARAMETERS = {
    "algorithm": "mmseqs2",
    "databases": ["small_bfd"],
    "e_value": 0.0001,
    "iterations": 1,
    "relax_prediction": True,
    "structure_model_preset": "monomer",
    "structure_models_to_relax": "all",
    "num_predictions_per_model": 1,
    "template_searcher": "hhsearch"
}
```

**Parameter Validation Rules:**
- `algorithm`: Must be `"mmseqs2"` or `"jackhmmer"`
- `databases`: Array of strings, must be from: `["uniref90", "mgnify", "small_bfd", "bfd", "uniclust30"]`
- `e_value`: Positive float, typically 0.0001 to 0.001
- `iterations`: Integer 1-3
- `relax_prediction`: Boolean
- `structure_model_preset`: Must be `"monomer"` or `"multimer"`
- `structure_models_to_relax`: Must be `"all"`, `"best"`, or `"none"`
- `num_predictions_per_model`: Positive integer, typically 1-5
- `template_searcher`: String, typically `"hhsearch"`

**UI Parameter Configuration:**
- Provide UI dialog (similar to RFdiffusionDialog) for parameter configuration
- Show advanced/collapsed section for optional parameters
- Provide preset configurations:
  - **Fast**: `mmseqs2`, `["small_bfd"]`, `iterations=1`, `relax_prediction=False`
  - **Balanced** (default): `mmseqs2`, `["small_bfd"]`, `iterations=1`, `relax_prediction=True`
  - **Accurate**: `jackhmmer`, `["uniref90", "mgnify", "small_bfd"]`, `iterations=2`, `relax_prediction=True`
- Allow custom parameter configuration
- Save user preferences for future jobs

---

## 4. Error Handling

### 4.1 Error Categories

**User-Friendly Error Messages:**
- Translate technical API errors to user-friendly messages
- Provide expandable technical details for debugging
- Include actionable recovery suggestions

**Error Types:**
1. **Validation Errors**: Invalid sequence, too long/short, non-standard amino acids
2. **Authentication Errors**: Missing/invalid API key (401, 403)
3. **Rate Limiting**: 429 responses - show user-friendly message, manual retry
4. **Network Errors**: Connection failures, timeouts - retry with backoff
5. **API Errors**: 4xx/5xx responses - parse and display user-friendly message
6. **Timeout Errors**: Jobs exceeding max wait time - fail gracefully, allow resubmission
7. **Polling Errors**: Transient failures during polling - retry with backoff

### 4.2 Error Recovery

**Hybrid Approach:**
- **In-Memory**: Active jobs tracked in handler's `active_jobs` dict
- **Database**: Job history and metadata stored in database for recovery
- **Session Association**: Jobs linked to sessions for context

**Recovery Scenarios:**
1. **Network Interruption**: Resume polling when connection restored
2. **Server Restart**: Recover active jobs from database on startup
3. **User Navigation**: Jobs continue in background, status available on return
4. **Duplicate Requests**: Detect and handle simultaneous identical requests

**Error Display:**
- Use existing `ErrorDisplay` component (tool-specific optimizations allowed)
- Show user-friendly message with expandable technical details
- Provide retry button for appropriate error types

---

## 5. Progress Tracking

### 5.1 Real-Time Updates

**WebSocket/SSE Implementation:**
- Use WebSocket or Server-Sent Events (SSE) for real-time progress
- Push updates from handler to frontend as polling progresses
- Update `ProgressTracker` component in real-time

**Progress Indicators:**
- **Time-Based Estimates**: Show elapsed time and estimated remaining time
- **Stage-Based Progress**: Display current stage (MSA Search → Structure Prediction → Relaxation)
- **Simple Spinner**: Fallback with elapsed time if detailed progress unavailable
- **Combined Approach**: Use multiple indicators for better UX

**Progress Callback Pattern:**
```python
def progress_callback(message: str, progress: float):
    # Send via WebSocket/SSE to frontend
    # progress: 0-100 float
    # message: Human-readable status
```

### 5.2 Progress Estimation

**NVIDIA API Limitation:**
- API doesn't provide detailed progress percentages
- Estimate based on:
  - Elapsed time vs. estimated total time
  - Sequence length (longer = more time)
  - Polling iteration count

**Estimation Formula:**
- Base time: 2-5 min (<100 residues), 5-15 min (100-300), 15-30 min (300-600), 30-60 min (600+)
- Progress = min(90, 10 + (poll_count * 2) + (elapsed_time / estimated_total * 70))

---

## 6. File Storage & Results

### 6.1 Storage Structure

**Directory Organization:**
- Results directory: `server/alphafold_results/` (separate from RFdiffusion)
- User-scoped storage: Use existing `save_result_file()` function
- File naming: `alphafold_{job_id}.pdb`

**File Storage Function:**
```python
filepath = save_result_file(
    user_id=user_id,
    file_id=job_id,
    file_type="alphafold",
    filename=f"alphafold_{job_id}.pdb",
    content=pdb_content.encode("utf-8"),
    job_id=job_id,
                    metadata={
                        "sequence_length": len(sequence),
                        "parameters": {
                            "algorithm": algorithm,
                            "databases": databases,
                            "e_value": e_value,
                            "iterations": iterations,
                            "relax_prediction": relax_prediction,
                            "structure_model_preset": structure_model_preset,
                            "structure_models_to_relax": structure_models_to_relax,
                            "num_predictions_per_model": num_predictions_per_model,
                            "template_searcher": template_searcher,
                        },
                        "job_id": job_id,
                    },
)
```

### 6.2 Metadata Storage

**Store Alongside PDB:**
- Sequence (original input)
- Parameters (relax_prediction)
- Job metadata (job_id, timestamp, user_id, session_id)
- Result metadata (filepath, size, processing time)

**Database Schema:**
- Extend existing job tracking table or create `alphafold_jobs` table
- Fields: job_id, user_id, session_id, sequence, parameters, status, result_filepath, created_at, completed_at, error_message

### 6.3 Result Loading

**Automatic MolStar Integration:**
- Automatically load completed PDB into MolStar viewer
- Use existing `MolstarBuilder` integration
- Associate with current session for context

---

## 7. Session & Context Integration

### 7.1 Session Association

**Auto-Associate with Sessions:**
- All AlphaFold jobs automatically linked to active chat session
- Use `associate_file_with_session()` function
- Enable job history in chat interface

**Session Tracking:**
```python
if session_id and user_id:
    associate_file_with_session(
        session_id=str(session_id),
        file_id=job_id,
        user_id=user_id,
        file_type="alphafold",
        file_path=filepath,
        filename=filename,
        size=len(pdb_content),
        job_id=job_id,
        metadata={...},
    )
```

### 7.2 Chat Integration

**Agent Routing:**
- Use same agent routing pattern as RFdiffusion
- Trigger keywords: "fold", "dock", "predict structure", "alphafold"
- Agent responds with confirmation dialog
- User confirms → job submission → progress tracking

**Chat History:**
- Show job status in chat messages
- Display results when completed
- Allow referencing previous results in new requests

### 7.3 Context Extraction

**Sequence Sources:**
1. Direct sequence input: `"fold MVLSEGEWQL..."`
2. PDB ID: `"fold PDB:1ABC"`
3. Chain-specific: `"fold chain A from PDB:1HHO"`
4. Residue range: `"fold residues 50-100 from chain A"`
5. Uploaded file: Extract from uploaded PDB file
6. MolStar viewer: Extract from currently loaded structure (future enhancement)

---

## 8. Performance & Scalability

### 8.1 Request Management

**Request Queuing:**
- Implement job queue for high-load scenarios
- Queue jobs when too many concurrent requests
- Process queue with priority (shorter sequences first)

**Concurrent Job Limits:**
- Limit concurrent jobs per user (configurable, default: 3)
- Limit total concurrent jobs system-wide (configurable, default: 10)
- Reject new jobs with friendly message when limits reached

### 8.2 Connection Management

**Connection Pooling:**
- Use aiohttp connection pool for API requests
- Reuse connections for polling requests
- Configure pool size based on expected load

**Memory Management:**
- Optimize polling connections (don't hold unnecessary data)
- Clean up completed jobs from memory after result retrieval
- Store only active jobs in memory, archive to database

### 8.3 Caching Strategy

**Result Caching:**
- Cache results for identical sequences (hash-based)
- Check cache before submitting new job
- Return cached result immediately if available
- Cache TTL: 30 days (configurable)

---

## 9. Monitoring & Observability

### 9.1 Logging

**Comprehensive API Logging:**
- Log all API requests/responses (like RFdiffusion)
- Log file: `server/agents/handlers/logs/alphafold_api.log`
- Include: job_id, sequence preview, parameters, request/response, timing

**Log Format:**
```
=== AlphaFold Job Started ===
Job ID: {job_id}
Sequence Length: {length}
Sequence Preview: {first_50_chars}...
Parameters: {json}
=== NVIDIA API Request ===
URL: {endpoint}
Payload: {json}
=== NVIDIA API Response ===
Status: {status}
Response: {json}
```

**Sensitive Data Handling:**
- Sanitize API keys in logs (mask with `***`)
- Log sequence previews (first 50 chars) not full sequences
- Log job metadata, not raw PDB content

### 9.2 Metrics Tracking

**Job Metrics:**
- Success rate (completed / total)
- Average processing time by sequence length
- Failure rate by error type
- API response times
- Polling iteration counts

**User Metrics:**
- Jobs per user
- Average jobs per session
- Most common sequence lengths
- Peak usage times

**System Metrics:**
- Concurrent job count
- Queue depth
- API rate limit hits
- Error rate trends

### 9.3 Admin Dashboard Integration

**Dashboard Features:**
- Real-time job monitoring
- Job history and analytics
- Error rate tracking
- User activity metrics
- API usage statistics
- Alert configuration

**Alerts:**
- High failure rate (>5% in last hour)
- Long-running jobs (>45 minutes)
- API rate limit approaching
- System queue depth >10

---

## 10. Testing Strategy

### 10.1 Integration Tests

**Test Coverage:**
- End-to-end job submission and completion
- Polling logic with mock 202/200 responses
- Error scenarios (rate limits, timeouts, network failures)
- Sequence extraction from various sources
- Result parsing and file storage
- Session association

**Test Approach:**
- Mock NVIDIA API responses for predictable testing
- Test with real API calls in staging environment
- Simulate polling scenarios (202 → 200)
- Test error recovery and retry logic

### 10.2 Unit Tests

**Component Tests:**
- Sequence validation (various inputs, edge cases)
- Parameter normalization
- Error message translation
- Progress estimation calculations
- File storage operations

### 10.3 Edge Case Testing

**Critical Edge Cases:**
- Duplicate simultaneous requests (same sequence, same user)
- Very short sequences (<20 residues) - should reject
- Very long sequences (>4000 chars) - should reject
- Sequences with whitespace/special characters - should normalize
- Network interruptions during polling - should recover
- Server restart during active jobs - should recover from DB

**Deferred Edge Cases:**
- Batch folding (multiple sequences) - future enhancement
- API version changes - handle when encountered
- Flexible response parsing - already implemented

---

## 11. Implementation Plan

### 11.1 Phase 1: Base Class & Client Refactoring

**Tasks:**
1. Create `server/tools/nvidia/base.py` with `NVIDIAHealthClient` base class
2. Refactor `RFdiffusionClient` to inherit from base class
3. Create `AlphaFoldClient` inheriting from base class
4. Move polling logic from `NIMSClient` to `AlphaFoldClient`
5. Update imports and references

**Files to Create/Modify:**
- `server/tools/nvidia/base.py` (new)
- `server/tools/nvidia/alphafold.py` (new)
- `server/tools/nvidia/rfdiffusion.py` (refactor)
- `server/tools/nvidia/client.py` (deprecate or refactor)

### 11.2 Phase 2: Handler Refactoring

**Tasks:**
1. Refactor `AlphaFoldHandler` to use new `AlphaFoldClient`
2. Update parameter handling to support all API parameters (algorithm, databases, e_value, iterations, structure_model_preset, etc.)
3. Update sequence validation to 4096 char limit
4. Implement proper error handling with user-friendly messages
5. Add session association logic
6. Implement result storage in `server/alphafold_results/`

**Files to Modify:**
- `server/agents/handlers/alphafold.py` (refactor)

### 11.3 Phase 3: Real-Time Progress

**Tasks:**
1. Implement WebSocket/SSE endpoint for progress updates
2. Update `AlphaFoldHandler` to send progress via WebSocket/SSE
3. Update frontend `ProgressTracker` to receive real-time updates
4. Implement progress estimation logic
5. Add stage-based progress indicators

**Files to Create/Modify:**
- `server/app.py` (add WebSocket/SSE endpoint)
- `server/agents/handlers/alphafold.py` (add progress broadcasting)
- `src/components/ProgressTracker.tsx` (update for real-time)

### 11.4 Phase 4: Monitoring & Observability

**Tasks:**
1. Implement comprehensive API logging
2. Add metrics tracking (success rate, timing, errors)
3. Integrate with admin dashboard
4. Set up alerting for failures and long jobs
5. Add job history database schema

**Files to Create/Modify:**
- `server/agents/handlers/logs/alphafold_api.log` (logging)
- `server/domain/storage/job_tracking.py` (new, metrics)
- `src/pages/AdminDashboard.tsx` (add AlphaFold metrics)

### 11.5 Phase 5: Testing & Documentation

**Tasks:**
1. Write integration tests
2. Write unit tests for validation and parsing
3. Test edge cases
4. Update API documentation
5. Create user guide for AlphaFold feature

**Files to Create:**
- `tests/test_alphafold_integration.py`
- `tests/test_alphafold_client.py`
- `docs/ALPHAFOLD_USER_GUIDE.md`

---

## 12. API Endpoints

### 12.1 Existing Endpoints (Maintain)

**POST `/api/alphafold/fold`**
- Submit folding job
- Returns: 202 Accepted with job_id (for polling) or 200 with result (immediate)
- Request body: `{sequence, algorithm?, databases?, e_value?, iterations?, relax_prediction?, structure_model_preset?, structure_models_to_relax?, num_predictions_per_model?, template_searcher?, jobId, sessionId}`
- All parameters except `sequence` are optional and use API defaults if not provided

**GET `/api/alphafold/status/{job_id}`**
- Poll job status
- Returns: `{job_id, status, data?, error?}`
- Status: queued|running|completed|error|cancelled

**POST `/api/alphafold/cancel/{job_id}`**
- Cancel running job
- Returns: `{job_id, status: "cancelled"}`

### 12.2 New Endpoints

**WebSocket `/api/alphafold/progress/{job_id}`**
- Real-time progress updates
- Messages: `{job_id, progress, message, stage?}`

**GET `/api/alphafold/history`**
- Get user's job history
- Returns: `[{job_id, sequence_preview, status, created_at, completed_at, ...}]`

**GET `/api/alphafold/result/{job_id}`**
- Download result PDB file
- Returns: PDB file content

---

## 13. Configuration

### 13.1 Environment Variables

**Required:**
- `NVCF_RUN_KEY`: NVIDIA API key (required)

**Optional:**
- `ALPHAFOLD_URL`: Override API endpoint (default: `https://health.api.nvidia.com/v1/biology/deepmind/alphafold2`)
- `STATUS_URL`: Override status endpoint (default: `https://health.api.nvidia.com/v1/status`)
- `POLL_INTERVAL`: Polling interval in seconds (default: 10)
- `NIMS_MAX_POLLS`: Max polling iterations, 0=unlimited (default: 0)
- `NIMS_MAX_WAIT_SECONDS`: Max wait time in seconds (default: 1800)
- `NIMS_REQUEST_TIMEOUT`: Request timeout in seconds (default: 180)
- `NIMS_POST_RETRIES`: Retry count for POST requests (default: 3)
- `ALPHAFOLD_MAX_CONCURRENT_PER_USER`: Max concurrent jobs per user (default: 3)
- `ALPHAFOLD_MAX_CONCURRENT_TOTAL`: Max total concurrent jobs (default: 10)
- `ALPHAFOLD_CACHE_TTL_DAYS`: Result cache TTL in days (default: 30)

### 13.2 Feature Flags

**Feature Flag Support:**
- `ENABLE_ALPHAFOLD`: Enable/disable AlphaFold feature (default: true)
- `ALPHAFOLD_REAL_TIME_PROGRESS`: Enable real-time progress (default: true)
- `ALPHAFOLD_RESULT_CACHING`: Enable result caching (default: true)

---

## 14. Migration Strategy

### 14.1 Backward Compatibility

**Maintain Existing Endpoints:**
- Keep `/api/alphafold/fold` endpoint signature
- Support all documented API parameters
- Maintain backward compatibility with existing parameter names
- Add new optional parameters without breaking existing calls

### 14.2 Incremental Migration

**Migration Steps:**
1. Deploy base class and new client (Phase 1)
2. Update handler to use new client (Phase 2)
3. Add real-time progress (Phase 3)
4. Add monitoring (Phase 4)
5. Remove old `NIMSClient` after verification (Phase 5)

**Rollback Plan:**
- Keep old `NIMSClient` until new implementation verified
- Feature flag to switch between old/new implementations
- Database migration scripts for job history

---

## 15. Success Criteria

### 15.1 Functional Requirements

- ✅ AlphaFold2 jobs submit successfully via NVIDIA API
- ✅ Polling works correctly for long-running jobs
- ✅ Real-time progress updates displayed in UI
- ✅ Results automatically loaded into MolStar viewer
- ✅ Jobs associated with chat sessions
- ✅ Error handling provides user-friendly messages
- ✅ File storage uses user-scoped directories

### 15.2 Performance Requirements

- ✅ Jobs complete within expected timeframes (2-60 minutes based on length)
- ✅ Polling doesn't block other requests
- ✅ Concurrent job limits enforced
- ✅ Memory usage optimized for long-running jobs

### 15.3 Quality Requirements

- ✅ Integration tests pass
- ✅ Unit tests cover validation and parsing
- ✅ Error scenarios handled gracefully
- ✅ Comprehensive logging for debugging
- ✅ Metrics tracked for monitoring
- ✅ Admin dashboard shows AlphaFold metrics

---

## 16. Open Questions & Future Enhancements

### 16.1 Future Enhancements

- **Batch Folding**: Support multiple sequences in one request
- **MolStar Integration**: Extract sequences directly from viewer
- **Result Comparison**: Compare multiple folding results
- **Template Support**: Use existing structures as templates (if API supports)
- **Parameter Presets**: Create common parameter presets (fast, accurate, balanced) for users
- **Parameter Templates**: Save and reuse parameter configurations

### 16.2 Research Needed

- **API Testing**: Verify actual API response format with real requests
- **Parameter Optimization**: Test parameter combinations for optimal results
- **Default Parameter Tuning**: Optimize default values based on usage patterns
- **Performance Optimization**: Optimize polling intervals based on actual job times
- **Caching Strategy**: Evaluate cache hit rates and effectiveness

---

## 17. References

- [NVIDIA AlphaFold2 API Documentation](https://docs.api.nvidia.com/nim/reference/deepmind-alphafold2)
- Existing RFdiffusion integration: `server/tools/nvidia/rfdiffusion.py`
- Existing AlphaFold handler: `server/agents/handlers/alphafold.py`
- Existing NIMS client: `server/tools/nvidia/client.py`
- Architecture documentation: `ARCHITECTURE.md`

---

## 18. Appendix: Code Structure

### 18.1 File Organization

```
server/
├── tools/nvidia/
│   ├── base.py                 # NVIDIAHealthClient base class
│   ├── alphafold.py            # AlphaFoldClient (new)
│   ├── rfdiffusion.py          # RFdiffusionClient (refactored)
│   └── proteinmpnn.py          # ProteinMPNNClient (existing)
├── agents/handlers/
│   ├── alphafold.py            # AlphaFoldHandler (refactored)
│   └── rfdiffusion.py          # RFdiffusionHandler (existing)
├── domain/storage/
│   ├── job_tracking.py         # Job history and metrics (new)
│   └── file_access.py          # File storage utilities (existing)
└── alphafold_results/          # Result storage directory (new)
```

### 18.2 Key Classes

**NVIDIAHealthClient (base.py):**
- `__init__(api_key)`: Initialize with API key
- `_get_headers()`: Get common headers
- `_create_session()`: Create aiohttp session
- `_handle_error()`: Common error handling

**AlphaFoldClient (alphafold.py):**
- Inherits from `NVIDIAHealthClient`
- `validate_sequence(sequence)`: Validate sequence (≤4096 chars, standard amino acids)
- `validate_parameters(params)`: Validate all optional parameters
- `create_request_payload(sequence, **params)`: Create API request payload with defaults
- `submit_folding_request(sequence, progress_callback, **params)`: Submit and poll with all parameters
- `_poll_for_results(session, req_id, progress_callback)`: Polling logic
- `extract_pdb_from_result(result_data)`: Extract PDB from response

**AlphaFoldHandler (handlers/alphafold.py):**
- `process_folding_request(input_text, context)`: Parse and validate request
- `submit_folding_job(job_data)`: Submit job via client
- `get_job_status(job_id)`: Get job status
- `cancel_job(job_id)`: Cancel job

---

**End of Specification**
