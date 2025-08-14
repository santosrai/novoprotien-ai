# NovoProtein AI - Project Memory

## Project Overview
A molecular visualization application integrating MolStar viewer with AI-powered protein analysis. Features chat-based interaction, code execution, and 3D protein structure visualization.

## Recent Development Progress (Current Branch: feature/molstar-spec-integration)

### Latest Changes (Last 2 Commits)
**Commit c57d0e7**: feat: implement proper residue/chain selector syntax for MolStar integration
**Commit 673c8b5**: Enhance ChatPanel to render JSON and table formats for messages; improve CodeExecutor to reuse MolstarBuilder instance for better performance; update clearStructure method in molstarBuilder to ensure all existing structures are removed before loading new ones.

### Key Files Modified Recently:
- `src/components/ChatPanel.tsx` - Enhanced message rendering for JSON/table formats
- `src/components/MolstarViewer.tsx` - MolStar integration improvements
- `src/utils/codeExecutor.ts` - Performance optimizations with MolstarBuilder reuse
- `src/utils/molstarBuilder.ts` - Improved structure clearing and residue/chain selection
- `src/utils/api.ts` - API utilities
- `src/utils/examples.ts` - Example data/code
- `server/` files - Backend agent system with RAG capabilities
  - `agents.py` - AI agent implementations
  - `mvs_rag.py` - Retrieval-augmented generation for molecular data
  - `router_graph.py` - Request routing logic
  - `runner.py` - Main execution runner
  - `server.mjs` - Server implementation

### Current Architecture:
- **Frontend**: React + TypeScript + Vite + TailwindCSS
- **Backend**: Python agents with Node.js server
- **Molecular Viewer**: MolStar integration
- **AI Features**: Chat interface with code execution capabilities
- **Data**: PDB structure handling, UniProt integration

### Key Features Implemented:
1. **MolStar Integration**: 3D protein structure visualization
2. **Chat Interface**: AI-powered conversation with structured message rendering
3. **Code Execution**: Dynamic code execution with molecular data
4. **Residue/Chain Selection**: Proper syntax for MolStar structure manipulation
5. **Performance Optimizations**: Efficient MolstarBuilder instance reuse
6. **RAG System**: Retrieval-augmented generation for protein data queries

### Working Tree Status:
- Clean working directory (no uncommitted changes)
- All recent work committed and pushed to feature branch
- Ready for continued development or merge to main

### Development Environment:
- Node.js project with package.json configuration
- Python backend with requirements.txt
- Vite development server for frontend
- Git repository with feature branch workflow