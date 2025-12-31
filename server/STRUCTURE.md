# Server Directory Structure

## Overview

The server directory has been refactored from a flat structure to a clean, scalable organization that separates concerns and makes it easy to add new agents, tools, and features.

**Last Updated:** December 29, 2024

## New Structure

\`\`\`
server/
├── __init__.py
├── app.py                    # FastAPI application entry point
│
├── api/                      # API Layer
│   ├── routes/              # API route handlers
│   └── middleware/          # API middleware
│
├── agents/                   # LLM Agents
│   ├── registry.py          # Agent registry and definitions
│   ├── router.py            # Request routing logic
│   ├── runner.py            # Agent execution engine
│   ├── handlers/            # Agent-specific handlers
│   └── prompts/             # System prompts (separated by agent)
│
├── domain/                   # Domain Logic
│   ├── pipeline/            # Pipeline domain
│   ├── protein/             # Protein domain
│   └── storage/             # Storage domain
│
├── tools/                    # External Tools & Clients
│   └── nvidia/              # NVIDIA NIMS API tools
│
├── memory/                   # Memory & RAG
│   └── rag/                 # Retrieval-Augmented Generation
│
└── infrastructure/           # Infrastructure & Utilities
\`\`\`

## File Mapping (Old → New)

| Old Location | New Location |
|-------------|--------------|
| \`agents.py\` | \`agents/registry.py\` + \`agents/prompts/*.py\` |
| \`router_graph.py\` | \`agents/router.py\` |
| \`runner.py\` | \`agents/runner.py\` |
| \`alphafold_handler.py\` | \`agents/handlers/alphafold.py\` |
| \`rfdiffusion_handler.py\` | \`agents/handlers/rfdiffusion.py\` |
| \`proteinmpnn_handler.py\` | \`agents/handlers/proteinmpnn.py\` |
| \`nims_client.py\` | \`tools/nvidia/client.py\` |
| \`rfdiffusion_client.py\` | \`tools/nvidia/rfdiffusion.py\` |
| \`proteinmpnn_client.py\` | \`tools/nvidia/proteinmpnn.py\` |
| \`pipeline_schema.py\` | \`domain/pipeline/schema.py\` |
| \`pipeline_context.py\` | \`domain/pipeline/context.py\` |
| \`pipeline_blueprint_generator.py\` | \`domain/pipeline/blueprint.py\` |
| \`sequence_utils.py\` | \`domain/protein/sequence.py\` |
| \`uniprot.py\` | \`domain/protein/uniprot.py\` |
| \`pdb_storage.py\` | \`domain/storage/pdb_storage.py\` |
| \`session_file_tracker.py\` | \`domain/storage/session_tracker.py\` |
| \`mvs_rag.py\` | \`memory/rag/mvs_rag.py\` |
| \`utils.py\` | \`infrastructure/utils.py\` |
| \`safety.py\` | \`infrastructure/safety.py\` |

## Import Path Updates

**Old imports (no longer work):**
\`\`\`python
from agents import agents
from router_graph import routerGraph
from utils import log_line
from alphafold_handler import alphafold_handler
\`\`\`

**New imports (use these):**
\`\`\`python
from agents.registry import agents
from agents.router import routerGraph
from infrastructure.utils import log_line
from agents.handlers.alphafold import alphafold_handler
\`\`\`

See MIGRATION_NOTES.md for complete import mapping.

## Architecture Principles

- **Separation of Concerns**: Each layer has a well-defined responsibility
- **Dependency Flow**: API → Agents → Tools/Domain → Infrastructure
- **No Circular Dependencies**: Clear dependency hierarchy

## Adding New Components

### Adding a New Agent
1. Create prompt: \`agents/prompts/new_agent.py\`
2. Register in \`agents/registry.py\`
3. Add routing in \`agents/router.py\` (if needed)
4. Add handler in \`agents/handlers/new_agent.py\` (if needed)

### Adding a New Tool
1. Create client in \`tools/category/client.py\`
2. Implement \`BaseTool\` interface
3. Use in domain handlers or agent handlers

## Common Tasks

- **Finding agent code**: \`agents/registry.py\`, \`agents/prompts/\`, \`agents/handlers/\`
- **Finding domain logic**: \`domain/pipeline/\`, \`domain/protein/\`, \`domain/storage/\`
- **Finding external tools**: \`tools/nvidia/\`, \`tools/uniprot/\`
- **Finding infrastructure**: \`infrastructure/utils.py\`, \`infrastructure/safety.py\`

## Benefits

1. Clear boundaries between layers
2. Easy testing of domain logic
3. Scalable patterns for adding new features
4. Better code discoverability
5. Reusable components

For detailed migration guide, see MIGRATION_NOTES.md
