# User Isolation Architecture - Implementation Summary

## Overview

This document summarizes the implementation of user isolation architecture, transforming the application from a global, session-based system to a fully user-isolated, database-backed architecture.

## Implementation Date
January 2025

## Architecture Changes

### Before (Global System)
- Files stored in global directories: `server/uploads/pdb/`, `server/rfdiffusion_results/`, etc.
- Session tracking in JSON file: `server/domain/storage/session_files.json`
- No user association for files or sessions
- Pipelines stored only in frontend localStorage
- No authentication required for file operations

### After (User-Isolated System)
- Files stored in user-scoped directories: `server/storage/{user_id}/`
- All metadata in database tables with user_id foreign keys
- Session tracking in database with user ownership
- Pipelines persisted in backend database
- All file operations require authentication and ownership verification

## Database Schema Changes

### New Tables Added

#### `user_files`
Stores metadata for all user files (uploads, results, etc.)
```sql
- id (TEXT PRIMARY KEY)
- user_id (TEXT, FOREIGN KEY → users.id)
- file_type (TEXT: 'upload', 'rfdiffusion', 'proteinmpnn', 'alphafold')
- original_filename (TEXT)
- stored_path (TEXT) - Relative path from server root
- size (INTEGER)
- metadata (TEXT) - JSON with atoms, chains, etc.
- job_id (TEXT) - For result files
- created_at (TIMESTAMP)
```

#### `chat_sessions`
Stores chat session metadata
```sql
- id (TEXT PRIMARY KEY)
- user_id (TEXT, FOREIGN KEY → users.id)
- title (TEXT)
- created_at, updated_at (TIMESTAMP)
```

#### `session_files`
Associates files with chat sessions
```sql
- session_id (TEXT, FOREIGN KEY → chat_sessions.id)
- file_id (TEXT, FOREIGN KEY → user_files.id)
- user_id (TEXT, FOREIGN KEY → users.id)
- created_at (TIMESTAMP)
- PRIMARY KEY (session_id, file_id)
```

#### `pipelines`
Stores pipeline definitions
```sql
- id (TEXT PRIMARY KEY)
- user_id (TEXT, FOREIGN KEY → users.id)
- name, description (TEXT)
- pipeline_json (TEXT) - Full pipeline definition
- status (TEXT: 'draft', 'running', 'completed', 'failed')
- created_at, updated_at (TIMESTAMP)
```

#### `pipeline_executions`
Tracks pipeline execution history
```sql
- id (TEXT PRIMARY KEY)
- pipeline_id (TEXT, FOREIGN KEY → pipelines.id)
- user_id (TEXT, FOREIGN KEY → users.id)
- status (TEXT)
- started_at, completed_at (TIMESTAMP)
- execution_log (TEXT) - JSON array
```

## File Storage Changes

### New Directory Structure
```
server/
└── storage/
    └── {user_id}/
        ├── uploads/
        │   └── pdb/
        ├── rfdiffusion_results/
        ├── proteinmpnn_results/
        │   └── {job_id}/
        └── alphafold_results/
```

### Updated Functions

#### `server/domain/storage/pdb_storage.py`
- `save_uploaded_pdb(filename, content, user_id)` - Now requires user_id, stores in user directory
- `get_uploaded_pdb(file_id, user_id)` - Verifies ownership
- `list_uploaded_pdbs(user_id)` - Filters by user
- `delete_uploaded_pdb(file_id, user_id)` - Verifies ownership before deletion

#### `server/domain/storage/session_tracker.py`
- `create_chat_session(user_id, title)` - Creates session in database
- `get_user_sessions(user_id)` - Lists user's sessions
- `associate_file_with_session(session_id, file_id, user_id, ...)` - Requires user_id
- `get_session_files(session_id, user_id)` - Verifies ownership
- `remove_file_from_session(session_id, file_id, user_id)` - Verifies ownership

#### New: `server/domain/storage/file_access.py`
- `verify_file_ownership(file_id, user_id)` - Ownership check
- `get_user_file_path(file_id, user_id)` - Get path with ownership check
- `get_file_metadata(file_id, user_id)` - Get metadata with ownership check
- `list_user_files(user_id, file_type)` - List user's files
- `save_result_file(user_id, file_id, file_type, ...)` - Save result files in user directory

## Handler Updates

### RFdiffusion Handler
- Updated to use `save_result_file()` from `file_access.py`
- Passes `user_id` from job_data to file storage
- Files saved to `storage/{user_id}/rfdiffusion_results/`

### AlphaFold Handler
- Updated to use `save_result_file()` from `file_access.py`
- Passes `user_id` from job_data to file storage
- Files saved to `storage/{user_id}/alphafold_results/`

### ProteinMPNN Handler
- Updated to use user-scoped results directory
- Results saved to `storage/{user_id}/proteinmpnn_results/{job_id}/`
- `get_job_result()` now accepts optional `user_id` parameter

## API Endpoint Changes

### File Endpoints (Now Require Authentication)

#### `POST /api/upload/pdb`
- **Added**: `user: Dict = Depends(get_current_user)`
- **Changed**: Passes `user["id"]` to `save_uploaded_pdb()`
- **Changed**: Passes `user["id"]` to `associate_file_with_session()`

#### `GET /api/upload/pdb/{file_id}`
- **Added**: `user: Dict = Depends(get_current_user)`
- **Changed**: Uses `get_uploaded_pdb(file_id, user["id"])` to verify ownership

#### `GET /api/sessions/{session_id}/files`
- **Added**: `user: Dict = Depends(get_current_user)`
- **Changed**: Uses `get_session_files(session_id, user["id"])` to verify ownership
- **Simplified**: Only returns files from database (no directory scanning)

#### `GET /api/sessions/{session_id}/files/{file_id}`
- **Added**: `user: Dict = Depends(get_current_user)`
- **Changed**: Uses database-backed file lookup with ownership verification
- **Simplified**: Uses `stored_path` from database entry

#### `GET /api/sessions/{session_id}/files/{file_id}/download`
- **Added**: `user: Dict = Depends(get_current_user)`
- **Changed**: Uses database-backed file lookup with ownership verification
- **Simplified**: Uses `stored_path` from database entry

#### `DELETE /api/sessions/{session_id}/files/{file_id}`
- **Added**: `user: Dict = Depends(get_current_user)`
- **Changed**: Uses database-backed file lookup with ownership verification
- **Changed**: Removes session association even if file doesn't exist on disk

#### `GET /api/proteinmpnn/result/{job_id}`
- **Added**: `user: Dict = Depends(get_current_user)`
- **Changed**: Passes `user["id"]` to `get_job_result()`
- **Changed**: Uses user-scoped directory with fallback to old location

### New API Endpoints

#### Pipeline Management (`/api/pipelines`)
- `POST /api/pipelines` - Create/save pipeline (requires auth)
- `GET /api/pipelines` - List user's pipelines (requires auth)
- `GET /api/pipelines/{pipeline_id}` - Get pipeline (verifies ownership)
- `PUT /api/pipelines/{pipeline_id}` - Update pipeline (verifies ownership)
- `DELETE /api/pipelines/{pipeline_id}` - Delete pipeline (verifies ownership)
- `POST /api/pipelines/{pipeline_id}/executions` - Create execution record
- `GET /api/pipelines/{pipeline_id}/executions` - List executions (verifies ownership)

#### Chat Session Management (`/api/chat/sessions`)
- `POST /api/chat/sessions` - Create session (requires auth)
- `GET /api/chat/sessions` - List user's sessions (requires auth)
- `GET /api/chat/sessions/{session_id}` - Get session (verifies ownership)
- `PUT /api/chat/sessions/{session_id}` - Update session (verifies ownership)
- `DELETE /api/chat/sessions/{session_id}` - Delete session (verifies ownership)

## Migration Script

### Location
`server/database/migrations/001_user_isolation.py`

### What It Does
1. Creates new database tables (via `init_db()`)
2. Migrates existing files:
   - Scans `server/uploads/pdb/` directory
   - Moves files to `server/storage/system/uploads/pdb/`
   - Creates `user_files` entries with `user_id = 'system'`
3. Migrates result files:
   - Creates database entries for existing RFdiffusion, AlphaFold, ProteinMPNN results
   - Keeps files in old locations for backward compatibility
4. Migrates session files:
   - Reads `session_files.json`
   - Creates `chat_sessions` entries (assigned to 'system' user)
   - Creates `session_files` associations

### Running the Migration
```bash
cd server
python database/migrations/001_user_isolation.py
```

### Post-Migration
- All migrated data is assigned to `user_id = 'system'`
- Admin tools can be used to reassign files to specific users
- Old file locations are preserved for backward compatibility

## Security Enhancements

1. **Authentication Required**: All file operations now require JWT authentication
2. **Ownership Verification**: Every file access verifies user ownership
3. **User-Scoped Directories**: File system structure prevents path traversal
4. **Database Foreign Keys**: CASCADE deletes ensure data integrity
5. **Session Ownership**: Session access requires ownership verification

## Backward Compatibility

### Temporary Support
- Old file locations are still checked as fallback
- ProteinMPNN handler checks both user-scoped and old locations
- Migration script preserves old files

### Deprecation Path
- Old endpoints will be deprecated in future versions
- Frontend should be updated to use new authenticated endpoints
- Old file locations can be cleaned up after migration period

## Testing Checklist

### File Operations
- [ ] Upload PDB file (requires auth)
- [ ] Download uploaded file (verifies ownership)
- [ ] List user's files
- [ ] Delete file (verifies ownership)
- [ ] Access denied for other user's files

### Session Operations
- [ ] Create chat session
- [ ] List user's sessions
- [ ] Associate file with session
- [ ] Get session files (verifies ownership)
- [ ] Delete session (verifies ownership)

### Pipeline Operations
- [ ] Create pipeline
- [ ] List user's pipelines
- [ ] Get pipeline (verifies ownership)
- [ ] Update pipeline (verifies ownership)
- [ ] Delete pipeline (verifies ownership)
- [ ] Create execution record
- [ ] List executions (verifies ownership)

### Result Files
- [ ] RFdiffusion results saved to user directory
- [ ] AlphaFold results saved to user directory
- [ ] ProteinMPNN results saved to user directory
- [ ] Results accessible only by owner

## Files Modified

### Backend
- `server/database/schema.sql` - Added new tables
- `server/domain/storage/pdb_storage.py` - User-scoped storage
- `server/domain/storage/session_tracker.py` - Database-backed sessions
- `server/domain/storage/file_access.py` - **NEW** - Access control utilities
- `server/app.py` - Added auth to endpoints, registered new routes
- `server/agents/handlers/rfdiffusion.py` - User-scoped file saving
- `server/agents/handlers/alphafold.py` - User-scoped file saving
- `server/agents/handlers/proteinmpnn.py` - User-scoped results directory
- `server/api/routes/pipelines.py` - **NEW** - Pipeline API
- `server/api/routes/chat_sessions.py` - **NEW** - Session API
- `server/database/migrations/001_user_isolation.py` - **NEW** - Migration script

### Frontend (Pending)
- `src/components/pipeline-canvas/store/pipelineStore.ts` - Backend sync needed
- `src/stores/chatHistoryStore.ts` - Backend sync needed
- `src/utils/api.ts` - Ensure auth headers on all requests

## Next Steps

1. **Run Migration**: Execute migration script on staging environment
2. **Test Endpoints**: Verify all endpoints work with authentication
3. **Update Frontend**: Sync pipeline and chat stores with backend
4. **Monitor**: Watch for any access denied errors
5. **Cleanup**: Remove old file locations after migration period

## Notes

- All existing files are assigned to 'system' user during migration
- Admin tools should be created to reassign files to specific users
- Frontend localStorage pipelines will sync to backend on next save
- Old session_files.json can be archived after migration
- Database foreign keys ensure data integrity with CASCADE deletes

