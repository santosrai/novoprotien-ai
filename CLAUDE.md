# Claude.md

The role of this file is to describe common mistakes and confusion points that agents might encounter as they work in this project. If you ever encounter something in the project that surprises you, please alert the developer working with you and indicate that this is the case in the AgentMD file to help prevent future agents from having the same issue.

## Known Architecture Surprises

### Agent Tool Maps (`server/agents/tools/__init__.py`)
The `AGENT_TOOL_MAP` controls which LangChain tools are available to each sub-agent. If a feature works in one agent context but not another, CHECK THIS MAP FIRST. For example, `get_smiles_tool` was only in `code_builder` but not `bio_chat`, causing "get smiles for uric acid" to silently fail in the main chat.

### `upload_pdb_from_content` endpoint (`server/api/routes/files.py`)
This endpoint previously forced all uploaded content to use `.pdb` extension, which would corrupt SDF files sent by the SMILES tool. Always check that SDF filenames are preserved as `.sdf` through the entire upload pipeline.

### FastAPI form uploads vs query params
Scalar parameters in multipart form uploads (e.g., `session_id`) must be annotated with `Form()` to be read from the request body. Without `Form()`, FastAPI only reads them from query parameters. Use URL query params (e.g., `/api/upload/pdb?session_id=...`) to avoid this ambiguity.

### Backend startup
Run from the project root: `python -m uvicorn server.app:app --reload`
Do NOT `cd server` first — relative imports break.