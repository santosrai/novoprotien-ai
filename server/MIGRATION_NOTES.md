# Server Structure Migration Notes

## What Changed?

The server directory was refactored from a flat structure to an organized, scalable architecture on **December 29, 2024**.

## Breaking Changes

### Import Paths

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

## Common Import Updates

| What You're Importing | Old Import | New Import |
|----------------------|------------|------------|
| Agent registry | \`from agents import agents\` | \`from agents.registry import agents\` |
| Router | \`from router_graph import routerGraph\` | \`from agents.router import routerGraph\` |
| Runner | \`from runner import run_agent\` | \`from agents.runner import run_agent\` |
| Utilities | \`from utils import log_line\` | \`from infrastructure.utils import log_line\` |
| Safety | \`from safety import violates_whitelist\` | \`from infrastructure.safety import violates_whitelist\` |
| AlphaFold handler | \`from alphafold_handler import alphafold_handler\` | \`from agents.handlers.alphafold import alphafold_handler\` |
| NIMS client | \`from nims_client import NIMSClient\` | \`from tools.nvidia.client import NIMSClient\` |
| PDB storage | \`from pdb_storage import save_uploaded_pdb\` | \`from domain.storage.pdb_storage import save_uploaded_pdb\` |
| Sequence utils | \`from sequence_utils import SequenceExtractor\` | \`from domain.protein.sequence import SequenceExtractor\` |
| Pipeline schema | \`from pipeline_schema import PipelineBlueprint\` | \`from domain.pipeline.schema import PipelineBlueprint\` |

## Troubleshooting

### Import Errors
1. Clear Python cache: \`find . -type d -name __pycache__ -exec rm -r {} +\`
2. Verify you're using the new import paths
3. Check STRUCTURE.md for correct file locations

### Can't Find a File?
1. Check the file mapping table in STRUCTURE.md
2. Use your IDE's "Go to Definition" feature
3. Search by function/class name across the codebase

See STRUCTURE.md for complete documentation.
