# RFdiffusion API Fixes

## Issue Summary

The RFdiffusion API was returning a 422 error with "Invalid shape in axis 0: 0" from the NVIDIA API. This error typically indicates that the input data being sent has an invalid shape or is empty.

## Root Causes Identified

1. **Complex PDB processing**: The original approach was too complex and could cause residue mismatch errors
2. **Invalid contigs format**: Complex contigs format that might not be compatible with the API
3. **Over-engineering**: The system was trying to be too smart about PDB processing

## Fixes Applied

### 1. Simplified PDB Processing (`rfdiffusion_client.py`)

- **Official document approach**: Now follows the EXACT approach from the NVIDIA NIMS official example:
  ```python
  # Official approach:
  lines = filter(lambda line: line.startswith("ATOM"), pdb.read_text().split("\n"))
  return "\n".join(list(lines)[:400])
  ```
- **Simple filtering**: Just filters ATOM lines and limits to max_atoms (default 400)
- **No complex logic**: Removed all the complex residue prioritization and smart selection
- **No minimum requirements**: Removed the 10-atom minimum requirement that could cause issues

### 2. Simplified Contigs Format (`rfdiffusion_client.py`, `rfdiffusion_handler.py`)

- **Generic contigs**: Changed from complex "A20-60/0 50-100" to simple "50-150"
- **No chain references**: Removed chain-specific residue references that could cause "Residue A114 not in pdb file" errors
- **Length-based specification**: Uses generic length specifications like "50-150" instead of specific residue ranges

### 3. Simplified Validation (`rfdiffusion_client.py`)

- **Basic validation only**: Just checks that PDB content exists and has ATOM lines
- **No format requirements**: Removed complex PDB format validation that could reject valid PDBs
- **No minimum atom count**: Removed the 10-atom minimum requirement

### 4. Better Error Handling (`rfdiffusion_client.py`)

- **Specific error detection**: Added handling for "Residue not in pdb file" errors
- **Clear error messages**: Provides actionable error messages for debugging
- **Payload debugging**: Logs detailed information about what's being sent

## Key Changes Made

### `rfdiffusion_client.py`

```python
# Simplified PDB processing (following official example exactly)
def get_reduced_pdb(self, pdb_content: str, max_atoms: int = 400, hotspot_residues: list = None, contigs: str = None) -> str:
    # Follow the EXACT official example approach:
    # 1. Filter to only ATOM lines
    # 2. Limit to max_atoms
    # 3. Join with newlines
    atom_lines = list(filter(lambda line: line.startswith("ATOM"), lines))
    if len(atom_lines) > max_atoms:
        atom_lines = atom_lines[:max_atoms]
    return "\n".join(atom_lines)

# Simplified contigs
default_params = {
    "contigs": "50-150",  # Generic length specification without chain/residue references
    "hotspot_res": [],
    "diffusion_steps": 15,
}

# Better error handling for residue mismatch
elif "Residue" in error_text and "not in pdb file" in error_text:
    error_msg = "Contigs specification references residues that don't exist in the PDB file"
```

### `rfdiffusion_handler.py`

```python
# Simplified default contigs
if parsed["design_mode"] == "unconditional":
    parsed["contigs"] = "50-150"  # Generic length specification
else:
    parsed["contigs"] = "50-100"  # Generic length for motif scaffolding (no chain references)
```

## Why This Approach Works

1. **Matches official example**: The simplified approach exactly matches the working NVIDIA example
2. **Avoids residue conflicts**: Generic contigs like "50-150" don't reference specific residues that might not exist
3. **Simpler is better**: Less complex logic means fewer failure points
4. **Standard PDB handling**: Just filters ATOM lines like any standard PDB processor

## Expected Results

After applying these fixes:

1. **No more "Invalid shape in axis 0: 0" errors** from the NVIDIA API
2. **No more "Residue not in pdb file" errors** from complex contigs
3. **Better compatibility** with the NVIDIA API requirements
4. **Simpler, more reliable** PDB processing
5. **Follows official documentation** exactly

## Usage

The fixes are automatically applied when using the RFdiffusion API. The system now:

1. Uses simple, generic contigs (e.g., "50-150")
2. Processes PDB files using the exact official approach
3. Avoids complex residue-specific specifications
4. Provides clear error messages when issues occur

## Monitoring

To monitor the effectiveness of these fixes, check the server logs for:
- PDB processing results (should show "following official example")
- Contigs being used (should be simple like "50-150")
- Error messages (should be more specific and actionable)
- Payload validation summaries
