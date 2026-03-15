# Protein Label System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a scoped protein label system (`U1`, `P1`, `P2`, …) so uploads and designed proteins can be referenced consistently across chat, backend APIs, and the 3D visualizer.

**Architecture:** Store protein labels as session-scoped records in SQLite, linked to existing `user_files` / job records, then expose them via REST endpoints and wire them into the design/folding handlers. Frontend keeps a per-session list of labeled entities, which the visualizer and comparison UI use as their source of truth.

**Tech Stack:** FastAPI, sqlite3, custom migration scripts, React + TypeScript + React Query + Zustand.

---

### Task 1: Add DB schema for protein labels

**Files:**

- Modify: `server/database/schema.sql`
- Create: `server/database/migrations/006_protein_labels.py`

**Step 1: Define `protein_labels` table in `schema.sql`**

- Add a table with columns:
  - `id TEXT PRIMARY KEY`
  - `user_id TEXT NOT NULL`
  - `session_id TEXT NOT NULL`
  - `short_label TEXT NOT NULL` (e.g. `P1`, `U3`)
  - `kind TEXT NOT NULL` (`'upload'`, `'design'`, `'folded'`, etc.)
  - `source_tool TEXT` (`'upload'`, `'ProteinMPNN'`, `'OpenFold2'`, etc.)
  - `file_id TEXT` (nullable, FK to `user_files.id`)
  - `job_id TEXT` (nullable; for long-running jobs like AlphaFold)
  - `metadata TEXT` (JSON)
  - `created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP`
  - `updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP`
- Add FKs referencing `users(id)`, `chat_sessions(id)` (or `conversations(id)` if we decide to scope by conversation instead), and `user_files(id)` where applicable.
- Add a **unique constraint** on `(session_id, short_label)` to prevent label duplication within a session.
- Add indexes on `user_id`, `session_id`, and `short_label` for lookup performance.

**Step 2: Add migration script `006_protein_labels.py`**

- Follow the pattern from `004_alphafold_jobs.py` / `005_normalize_pipelines.py`:
  - Determine `DB_PATH` similarly.
  - Connect with `sqlite3.connect(str(DB_PATH))` and `row_factory = sqlite3.Row`.
  - Check `sqlite_master` for an existing `protein_labels` table and no-op if found.
  - Execute a `CREATE TABLE IF NOT EXISTS protein_labels (...)` statement matching the schema from `schema.sql`.
  - Create indexes and unique constraints.
- Expose a `run_migration()` function and a `__main__` guard so the script can be run standalone.

**Step 3: Verify migration wiring**

- Ensure `server/database/migrate.py` discovers and runs `006_protein_labels.py` (it should pick up numeric migrations automatically; confirm naming convention).
- Run the migration locally (e.g. via `python -m server.database.migrations.006_protein_labels` or `python server/database/migrate.py`) and inspect the DB to confirm table creation.

### Task 2: Implement backend helpers for label generation and CRUD

**Files:**

- Create: `server/domain/storage/protein_labels.py`

**Step 1: Implement row → dict helper**

- Mirror `_row_to_dict` implementations from `session_tracker.py` / `pdb_storage.py` to safely convert `sqlite3.Row` to `dict`.

**Step 2: Implement `generate_next_label`**

- Function signature:
  - `def generate_next_label(session_id: str, user_id: str, kind: str, prefix: str) -> str:`
- Behavior:
  - Query `protein_labels` for rows with `session_id = ?` and `short_label LIKE ?` where pattern is `f"{prefix}%"`.
  - Parse numeric suffixes, track the max `n`, and return `f"{prefix}{n+1}"`; default to `f"{prefix}1"` if none exist.
  - Do not commit; defer to the caller’s transaction.

**Step 3: Implement `register_protein_label`**

- Function signature:
  - `def register_protein_label(session_id, user_id, kind, source_tool, file_id=None, job_id=None, metadata=None, preferred_prefix=None) -> dict:`
- Behavior:
  - Choose prefix:
    - If `preferred_prefix` provided, use it.
    - Else: `'U'` for `kind == 'upload'`, `'P'` otherwise.
  - Within a `with get_db() as conn` block:
    - Verify session belongs to user (`chat_sessions` or `conversations` as appropriate).
    - Optionally verify `file_id` exists in `user_files` for this user.
    - In a small retry loop (e.g. up to 3 attempts):
      - Generate `short_label` via `generate_next_label`.
      - Insert into `protein_labels` with a new UUID `id`.
      - On uniqueness violation for `(session_id, short_label)`, retry with the next number.
  - Return the inserted row as a dict (including `short_label`).

**Step 4: Implement query helpers**

- `get_protein_labels_for_session(session_id: str, user_id: str) -> list[dict]`
- `get_protein_label_by_short_label(session_id: str, user_id: str, short_label: str) -> Optional[dict]`
- Each uses `get_db()` and `_row_to_dict`.

### Task 3: Add REST API for protein labels

**Files:**

- Create: `server/api/routes/proteins.py`
- Modify: `server/app.py` (to include the new router)

**Step 1: Implement router and endpoints**

- `APIRouter(prefix="/api/proteins", tags=["proteins"])`.
- Endpoints:
  - `POST ""`:
    - Auth via `Depends(get_current_user)`.
    - Request body fields:
      - `sessionId` (required)
      - `kind` (required)
      - `sourceTool` (optional)
      - `fileId` / `jobId` / `metadata` (optional)
    - Call `register_protein_label` and return the created entity.
  - `GET ""`:
    - Query parameter `sessionId`.
    - Return all labels via `get_protein_labels_for_session`.
  - `GET "/{short_label}"`:
    - Path parameter `short_label`, query parameter `sessionId`.
    - Return the matching label via `get_protein_label_by_short_label`, 404 if not found or not owned by user.

**Step 2: Wire router into FastAPI app**

- In `server/app.py`, import `proteins` into the routes list and include its router with `app.include_router(proteins.router)`, mirroring patterns from other route modules.

### Task 4: Integrate label registration into existing flows (uploads & designs)

**Files:**

- Modify: upload-related route(s) (likely `server/api/routes/files.py` or similar)
- Modify: design/folding handlers (e.g. `server/agents/handlers/proteinmpnn.py`, `alphafold.py`, `openfold2.py`, `rfdiffusion.py`)

**Step 1: Hook into uploads**

- After a successful PDB/sequence upload:
  - We already know `user_id`, `session_id`, and `file_id` (via `user_files` / `session_files`).
  - Call `register_protein_label` with `kind="upload"`, `source_tool="upload"`, `file_id=file_id`.
  - Include the new label object in the HTTP response so the frontend can update its state (e.g. `{ ..., "proteinLabel": {...} }`).

**Step 2: Hook into design/folding handlers**

- For each handler that produces a new protein result (ProteinMPNN, AlphaFold, RFdiffusion, OpenFold2):
  - Identify or add the place where result files or sequences are persisted (e.g. a created `user_files` row or job record).
  - Call `register_protein_label` with `kind="design"` or `"folded"` and an appropriate `source_tool`, passing `file_id` and/or `job_id`.
  - Ensure the handler’s returned JSON includes:
    - An `entities` or `labels` field with at least the new label record.

**Step 3: Keep agent / JSON actions consistent**

- If agent responses already have a structured `action` payload consumed by `ChatPanel`, update those payloads to include a `proteinLabels` field listing all new labels created in a step.
- Document in the handler docstring how labels are generated and propagated to the frontend.

### Task 5: Frontend types, hooks, and store

**Files:**

- Modify: `src/types` or relevant shared types file (to add `ProteinLabel` / `ProteinEntity` type)
- Create: `src/hooks/queries/useProteinLabels.ts`
- Create: `src/hooks/mutations/useRegisterProteinLabel.ts`
- Modify: relevant store (e.g. `src/stores/appStore.ts` or a new `proteinStore.ts`)

**Step 1: Define `ProteinLabel` type**

- Fields:
  - `id`, `userId`, `sessionId`, `shortLabel`, `kind`, `sourceTool`, `fileId`, `jobId`, `metadata`, `createdAt`, `updatedAt`.

**Step 2: Implement React Query hooks**

- `useProteinLabels(sessionId: string)`:
  - `GET /api/proteins?sessionId=...`, keyed by `['proteinLabels', sessionId]`.
- `useRegisterProteinLabel()`:
  - `POST /api/proteins`, then invalidates the `['proteinLabels', sessionId]` query.

**Step 3: Add a small store slice**

- Optional but useful:
  - Keep a list of labels for the active session in Zustand so the visualizer and other components can subscribe without prop-drilling.

### Task 6: Visualizer / layer control integration

**Files:**

- Modify: 3D visualizer and layer control components (e.g. under `src/components/three-d-viewer` or similar; inspect exact file names first)

**Step 1: Source labels from hooks/store**

- For the current session:
  - Load `ProteinLabel[]` via `useProteinLabels(sessionId)` or the store.
  - Map labels to visualizer layers:
    - `label.shortLabel` as the display label (`P1`, `U1`, …).
    - `kind` / `sourceTool` for badges (`upload`, `ProteinMPNN`, `OpenFold2`, …).

**Step 2: Wire visibility toggles**

- When a layer is toggled:
  - Resolve from `ProteinLabel` → `file_id` / `job_id` → 3D structure data (existing code path for loading PDBs).
  - Ensure multiple labels can be visible simultaneously.

### Task 7: Comparison UI and agent alignment

**Files:**

- Modify: Chat/summary components that display comparison tables.
- Modify: agent prompts (e.g. `server/agents/prompts/*.txt`) to explain label semantics.

**Step 1: Ensure summaries reference labels**

- In components that show comparison tables:
  - Use `shortLabel` as keys/column headers instead of raw file names or IDs.
  - Expect agent outputs like “compare P1 and P2” and map them to `ProteinLabel` records via `/api/proteins/{shortLabel}` or the in-memory list.

**Step 2: Update agent prompts**

- Clarify to models:
  - Proteins in this session are referred to as `U1`, `P1`, `P2`, etc.
  - When describing or comparing proteins, always refer to them by their label.

### Task 8: Testing & verification

**Files:**

- New/updated tests under `server/tests/` and `src/tests/` if the project already uses them; otherwise, add targeted tests alongside code where appropriate.

**Step 1: Backend tests**

- Unit tests for:
  - `generate_next_label` numeric parsing and incrementing.
  - Uniqueness enforcement for `(session_id, short_label)` via attempted double insert.
  - `register_protein_label` happy-paths for uploads and designs.

**Step 2: Manual E2E checks**

- Scenario 1: Upload multiple PDBs in one session:
  - Expect `U1`, `U2`, `U3` in API responses and visualizer.
- Scenario 2: Generate multiple designs:
  - Expect `P1`, `P2`, `P3` consistently across chat, tables, and the visualizer.
- Scenario 3: Refresh and reload session:
  - Existing labels remain stable; no duplicates within the same session.

