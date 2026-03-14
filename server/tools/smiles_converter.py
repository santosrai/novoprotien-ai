"""
Convert SMILES to 3D structure (PDB or SDF) using RDKit.
Used by the SMILES-to-3D tool so the frontend can load small molecules in MolStar.
"""

from __future__ import annotations

import logging
from typing import Literal

logger = logging.getLogger(__name__)

try:
    from rdkit import Chem
    from rdkit.Chem import AllChem

    HAS_RDKIT = True
except ImportError:
    HAS_RDKIT = False


def smiles_to_structure(
    smiles: str,
    format: Literal["pdb", "sdf"],
) -> tuple[str, str]:
    """
    Convert a SMILES string to 3D structure content and a suggested filename.

    Args:
        smiles: SMILES string (e.g. "O=C1NC2=C(N1)C(=O)NC(=O)N2").
        format: Output format, "pdb" or "sdf".

    Returns:
        Tuple of (content: str, filename: str).

    Raises:
        ValueError: If SMILES is invalid or 3D embedding fails.
        RuntimeError: If RDKit is not installed.
    """
    if not HAS_RDKIT:
        raise RuntimeError(
            "RDKit is required for SMILES conversion. Install with: pip install rdkit"
        )

    s = (smiles or "").strip()
    if not s:
        raise ValueError("SMILES string is empty.")

    mol = Chem.MolFromSmiles(s)
    if mol is None:
        raise ValueError("Invalid SMILES string: could not parse.")

    mol = Chem.AddHs(mol)
    result = AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
    if result != 0:
        raise ValueError(
            "Failed to generate 3D coordinates for this molecule. "
            "Some structures (e.g. very large or constrained) may not embed successfully."
        )

    AllChem.MMFFOptimizeMolecule(mol, maxIters=200)

    if format == "pdb":
        content = Chem.MolToPDBBlock(mol)
        filename = "smiles_structure.pdb"
    elif format == "sdf":
        block = Chem.MolToMolBlock(mol)
        content = block.rstrip() + "\n$$$$\n"
        filename = "smiles_structure.sdf"
    else:
        raise ValueError(f"Unsupported format: {format}. Use 'pdb' or 'sdf'.")

    return (content, filename)
