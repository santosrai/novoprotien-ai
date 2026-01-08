# NovoProtein AI - Context & Instructions

## Project Overview
**NovoProtein AI** is a molecular visualization and protein design platform. It combines a natural language chat interface with advanced 3D visualization (Molstar) and AI-driven protein engineering tools (AlphaFold2, RFdiffusion, ProteinMPNN).

### Key Capabilities
- **Natural Language Interaction**: Chat with agents to load structures, run simulations, or query biological data.
- **3D Visualization**: Real-time rendering of proteins using Molstar, controllable via generated scripts.
- **Protein Design Pipeline**: Integrated workflows for structure prediction (AlphaFold), de novo design (RFdiffusion), and sequence design (ProteinMPNN) via NVIDIA NIMS APIs.
- **Visual Workflow Editor**: A node-based editor (Pipeline Canvas) for designing complex biological pipelines.

## Technical Architecture

### Frontend (`src/`)
- **Framework**: React 18, Vite, TypeScript.
- **State Management**: Zustand (persistence middleware used for local storage).
- **Styling**: Tailwind CSS.
- **3D Engine**: Molstar (`molstar`).
- **Code Editor**: Monaco Editor (`@monaco-editor/react`).
- **Pipeline Library**: `src/components/pipeline-canvas/` (Standalone, reusable DAG editor).

### Backend (`server/`)
- **Framework**: FastAPI (Python).
- **AI/LLM**: OpenRouter (Claude 3.5 Sonnet) for agentic reasoning and code generation.
- **Compute**: NVIDIA NIMS for heavy biological computation (AlphaFold, RFdiffusion).
- **Routing**: `server/router_graph.py` determines which agent handles a request.
- **Agents**: Defined in `server/agents.py` (e.g., `code-builder`, `alphafold-agent`, `bio-chat`).

## Development & Setup

### Prerequisites
- Node.js (v18+)
- Python 3.10+
- API Keys: OpenRouter (`OPENROUTER_API_KEY`), NVIDIA NIMS (`NVCF_RUN_KEY`), OpenAI (Optional, for embeddings).

### Installation
1.  **Frontend**:
    ```bash
    npm install
    ```
2.  **Backend**:
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # or .\.venv\Scripts\activate on Windows
    pip install -r server/requirements.txt
    ```

### Running the Project
- **Development (Both)**: `npm run dev:all` (Starts Vite on `:5173` and FastAPI on `:8787`).
- **Frontend Only**: `npm run dev`
- **Backend Only**: `npm run start:server`

## Coding Conventions

### Authentication **(CRITICAL)**
- **API Instance**: Use `import { api } from '../utils/api'` for standard JSON requests. It handles JWT injection automatically.
- **File Uploads/Fetch**: When using `fetch` directly (e.g., `FormData`), **YOU MUST** manually inject headers:
    ```typescript
    import { getAuthHeaders } from '../utils/api';
    const headers = getAuthHeaders();
    fetch('/api/endpoint', { headers, body: formData });
    ```

### State & Storage
- **User vs. Session**:
    - **Backend**: Store data keyed by `user_id` (persistent).
    - **LocalStorage**: Use `sessionId` for transient/cache data only.
- **Persistence**: Zustand stores use `persist` middleware. Be careful when modifying store structures.

### File Structure
- **Components**: `src/components/PascalCase.tsx`
- **Utilities**: `src/utils/camelCase.ts`
- **Stores**: `src/stores/camelCaseStore.ts`
- **Backend Agents**: `server/agents.py`
- **Backend Handlers**: `server/{service}_handler.py` (e.g., `alphafold_handler.py`)

## Key Files
- `ARCHITECTURE.md`: **READ THIS FIRST**. Detailed system mapping and data flow.
- `src/App.tsx`: Main layout and initialization.
- `src/components/ChatPanel.tsx`: Core interaction loop (User -> Agent -> Response).
- `server/router_graph.py`: Logic for routing prompts to specific agents.
- `server/agents.py`: System prompts and definitions for all backend agents.
- `src/utils/molstarBuilder.ts`: API wrapper for controlling the 3D viewer.

## Testing
- **Frontend**: `npm run test` (if configured).
- **Backend**: `pytest` (run from root or `server/`).
- **Linting**: `npm run lint`.

## Common Tasks
- **New Agent**: Add to `server/agents.py`, update `server/router_graph.py`.
- **New Pipeline Node**: Add JSON config to `src/components/pipeline-canvas/nodes/`, register in `types/index.ts`.
- **API Endpoint**: Add to `server/app.py`.
