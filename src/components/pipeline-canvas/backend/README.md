# Pipeline Canvas Backend

Python backend support for the pipeline-canvas library. Provides FastAPI routes for pipeline persistence and execution tracking.

## Requirements

- Python 3.8+
- FastAPI
- Pydantic

## Installation

The backend is included in the `@mesantosrai/pipeline-canvas` npm package. After installing the package:

```bash
npm install @mesantosrai/pipeline-canvas
```

The backend files are at `node_modules/@mesantosrai/pipeline-canvas/backend/python/`.

## Database Setup

1. Run the migration to create the required tables:

```bash
sqlite3 your_database.db < node_modules/@mesantosrai/pipeline-canvas/backend/python/migrations/001_pipelines.sql
```

Or copy the SQL from `backend/python/migrations/001_pipelines.sql` and run it against your database.

2. The migration creates:
   - `pipelines` table: id, user_id, message_id, conversation_id, name, description, pipeline_json, status, created_at, updated_at
   - `pipeline_executions` table: id, pipeline_id, user_id, status, started_at, completed_at, execution_log

## Integration

### Basic Setup (No Chat Tables)

If your app does not have `chat_messages`, `conversations`, or `chat_sessions` tables:

```python
from fastapi import FastAPI

# After copying backend to your project (see "Copying Backend" below):
from pipeline_backend.routes import create_pipeline_router

# Your get_db and get_current_user implementations
def get_db():
    # Yield a database connection (e.g., sqlite3)
    ...

def get_current_user():
    # Return {"id": user_id, ...} - your auth dependency
    ...

app = FastAPI()

# Mount the router with verify_message_ownership=False
router = create_pipeline_router(get_db, get_current_user, verify_message_ownership=False)
app.include_router(router)
```

### With Chat Integration

If your app has chat tables and you want to verify `message_id` and `conversation_id` ownership:

```python
router = create_pipeline_router(get_db, get_current_user, verify_message_ownership=True)
app.include_router(router)
```

### Auth Modes

The router supports three auth modes:

| Mode | Description | Use Case |
|------|-------------|----------|
| `required` (default) | Must be authenticated. 401 when no token. | Apps with login (backwards compatible) |
| `optional` | Use user when present; else `X-Session-Id` or `anonymous` | Mixed: logged-in and anonymous users |
| `disabled` | Never require auth; use `X-Session-Id` or `anonymous` | No-auth apps, demos, internal tools |

**Auth required (default):**

```python
router = create_pipeline_router(get_db, get_current_user, verify_message_ownership=False)
```

**No-auth (disabled):**

```python
router = create_pipeline_router(get_db, get_current_user=None, auth_mode="disabled")
# Frontend sends X-Session-Id header for per-session scope
```

**Optional auth (both logged-in and anonymous):**

```python
# Provide get_current_user_optional that returns user or None (use HTTPBearer(auto_error=False))
from fastapi.security import HTTPBearer
security_optional = HTTPBearer(auto_error=False)

async def get_current_user_optional(credentials = Depends(security_optional)):
    if not credentials: return None
    # validate token, return user or None
    ...

router = create_pipeline_router(
    get_db,
    get_current_user=None,
    auth_mode="optional",
    get_current_user_optional=get_current_user_optional,
)
```

**Parameters:** `session_header` (default `X-Session-Id`), `anonymous_id` (default `"anonymous"`)

### Copying Backend to Your Project

For a cleaner setup, copy the backend into your project:

```bash
mkdir -p server/pipeline_backend
cp -r node_modules/@mesantosrai/pipeline-canvas/backend/python/* server/pipeline_backend/
```

Then add the path to Python and import:

```python
import sys
sys.path.insert(0, 'server')
from pipeline_backend.routes import create_pipeline_router
from pipeline_backend.schema import PipelineBlueprint, validate_blueprint
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/pipelines | Create or update a pipeline |
| GET | /api/pipelines | List pipelines (optional: ?conversation_id=) |
| GET | /api/pipelines/{id} | Get a pipeline |
| PUT | /api/pipelines/{id} | Update a pipeline |
| DELETE | /api/pipelines/{id} | Delete a pipeline |
| POST | /api/pipelines/{id}/executions | Create execution record |
| GET | /api/pipelines/{id}/executions | List executions |

## Response Format

The router returns responses compatible with the pipeline-canvas frontend adapter:

- **Create**: `{ "status": "success", "pipeline": { "id": "..." }, "message": "..." }`
- **Get**: `{ "status": "success", "pipeline": { ... } }`
- **List**: `{ "status": "success", "pipelines": [ ... ] }`

## Schema Module

The `schema.py` module provides:

- `PipelineNodeBlueprint`, `PipelineBlueprint` - Pydantic models
- `validate_blueprint(blueprint)` - Returns list of validation errors
- `NODE_DEFINITIONS` - Node type definitions for validation
