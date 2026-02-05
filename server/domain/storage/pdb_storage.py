"""Utilities for storing and retrieving uploaded PDB files."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException

try:
    # Try relative import first (when running as module)
    from ...database.db import get_db
except ImportError:
    # Fallback to absolute import (when running directly)
    from database.db import get_db

BASE_DIR = Path(__file__).parent.parent.parent
STORAGE_DIR = BASE_DIR / "storage"


def _row_to_dict(row) -> Dict[str, object]:
    """Convert sqlite3.Row to dict safely."""
    if isinstance(row, sqlite3.Row):
        return {key: row[key] for key in row.keys()}
    elif isinstance(row, dict):
        return row
    else:
        return dict(row)


def _get_user_storage_dir(user_id: str) -> Path:
    """Get user-specific storage directory."""
    user_dir = STORAGE_DIR / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def _get_user_upload_dir(user_id: str) -> Path:
    """Get user-specific upload directory."""
    upload_dir = _get_user_storage_dir(user_id) / "uploads" / "pdb"
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def _analyze_pdb(content: str) -> Tuple[int, List[str], Dict[str, int]]:
    """Return atom count, list of chain identifiers, and residue counts per chain."""
    atoms = 0
    chains = set()
    chain_residues: Dict[str, set] = {}
    
    # Standard amino acid three-letter codes
    aa_codes = {
        'ALA', 'ARG', 'ASN', 'ASP', 'CYS', 'GLN', 'GLU', 'GLY', 'HIS', 'ILE',
        'LEU', 'LYS', 'MET', 'PHE', 'PRO', 'SER', 'THR', 'TRP', 'TYR', 'VAL'
    }
    
    for line in content.splitlines():
        if not line:
            continue
        record = line[:6].strip().upper()
        if record in {"ATOM", "HETATM"}:
            atoms += 1
            if len(line) >= 22:
                chain_id = line[21].strip() or "?"
                chains.add(chain_id)
                
                # Extract residue information for CA atoms (protein residues)
                if len(line) >= 26 and line[12:16].strip() == 'CA':
                    res_name = line[17:20].strip()
                    if res_name in aa_codes:
                        try:
                            res_seq = int(line[22:26].strip())
                            if chain_id not in chain_residues:
                                chain_residues[chain_id] = set()
                            chain_residues[chain_id].add(res_seq)
                        except (ValueError, IndexError):
                            pass
    
    # Convert sets to counts
    chain_residue_counts = {
        chain: len(residues) 
        for chain, residues in chain_residues.items()
    }
    
    return atoms, sorted(chain for chain in chains if chain), chain_residue_counts


def _suggest_rfdiffusion_contigs(chain_residue_counts: Dict[str, int]) -> str:
    """Suggest RFdiffusion contigs based on chain residue counts."""
    if not chain_residue_counts:
        return "50-150"  # Default generic contig
    
    # Get the first chain (usually chain A)
    first_chain = sorted(chain_residue_counts.keys())[0] if chain_residue_counts else None
    if not first_chain:
        return "50-150"
    
    residue_count = chain_residue_counts[first_chain]
    
    # Suggest contigs based on structure size
    if residue_count < 50:
        # Small structure - suggest full length
        return f"{first_chain}1-{residue_count}"
    elif residue_count < 150:
        # Medium structure - suggest middle portion
        start = max(1, residue_count // 4)
        end = min(residue_count, start + 100)
        return f"{first_chain}{start}-{end}"
    else:
        # Large structure - suggest a 100-residue window
        start = residue_count // 4
        end = start + 100
        return f"{first_chain}{start}-{end}"


def save_uploaded_pdb(filename: str, content: bytes, user_id: str) -> Dict[str, object]:
    """Persist an uploaded PDB file and return metadata about it."""
    if not filename.lower().endswith(".pdb"):
        raise HTTPException(status_code=400, detail="Only .pdb files are supported")

    text_content = content.decode("utf-8", errors="ignore")
    atoms, chains, chain_residue_counts = _analyze_pdb(text_content)
    
    # Calculate suggested RFdiffusion parameters
    suggested_contigs = _suggest_rfdiffusion_contigs(chain_residue_counts)
    total_residues = sum(chain_residue_counts.values())

    file_id = uuid.uuid4().hex
    stored_name = f"{file_id}.pdb"
    upload_dir = _get_user_upload_dir(user_id)
    stored_path = upload_dir / stored_name
    stored_path.write_bytes(content)

    # Store metadata in database
    metadata_dict = {
        "atoms": atoms,
        "chains": chains,
        "chain_residue_counts": chain_residue_counts,
        "total_residues": total_residues,
        "suggested_contigs": suggested_contigs,
    }
    
    stored_path_rel = str(stored_path.relative_to(BASE_DIR))
    
    with get_db() as conn:
        conn.execute(
            """INSERT INTO user_files 
               (id, user_id, file_type, original_filename, stored_path, size, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                file_id,
                user_id,
                "upload",
                filename,
                stored_path_rel,
                len(content),
                json.dumps(metadata_dict),
            ),
        )

    return {
        "file_id": file_id,
        "filename": filename,
        "stored_path": stored_path_rel,
        "size": len(content),
        "atoms": atoms,
        "chains": chains,
        "chain_residue_counts": chain_residue_counts,
        "total_residues": total_residues,
        "suggested_contigs": suggested_contigs,
    }


def get_uploaded_pdb(file_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, object]]:
    """Get uploaded PDB file metadata. If user_id provided, verifies ownership."""
    with get_db() as conn:
        query = "SELECT * FROM user_files WHERE id = ? AND file_type = 'upload'"
        params = [file_id]
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        
        row = conn.execute(query, params).fetchone()
        if not row:
            return None
        
        # Convert Row to dict safely
        metadata = _row_to_dict(row)
        
        stored_path = BASE_DIR / metadata["stored_path"]
        if not stored_path.exists():
            return None
        
        # Parse JSON metadata
        if metadata.get("metadata"):
            try:
                parsed_metadata = json.loads(metadata["metadata"])
                metadata.update(parsed_metadata)
            except json.JSONDecodeError:
                pass
        
        metadata["absolute_path"] = str(stored_path)
        return metadata


def list_uploaded_pdbs(user_id: str) -> List[Dict[str, object]]:
    """List all uploaded PDB files for a user."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM user_files 
               WHERE user_id = ? AND file_type = 'upload' 
               ORDER BY created_at DESC""",
            (user_id,),
        ).fetchall()
        
        results: List[Dict[str, object]] = []
        for row in rows:
            # Convert Row to dict safely
            metadata = _row_to_dict(row)
            
            stored_path = BASE_DIR / metadata["stored_path"]
            if not stored_path.exists():
                continue
            
            # Parse JSON metadata
            if metadata.get("metadata"):
                try:
                    parsed_metadata = json.loads(metadata["metadata"])
                    metadata.update(parsed_metadata)
                except json.JSONDecodeError:
                    pass
            
            try:
                stat = stored_path.stat()
                metadata["modified"] = stat.st_mtime
            except OSError:
                metadata["modified"] = None
            
            metadata["file_id"] = metadata["id"]
            results.append(metadata)
        
        return results


def delete_uploaded_pdb(file_id: str, user_id: str) -> None:
    """Delete uploaded PDB file. Verifies ownership before deletion."""
    with get_db() as conn:
        # Get file info and verify ownership
        row = conn.execute(
            """SELECT stored_path FROM user_files 
               WHERE id = ? AND user_id = ? AND file_type = 'upload'""",
            (file_id, user_id),
        ).fetchone()
        
        if not row:
            return
        
        # Delete file from filesystem
        stored_path = BASE_DIR / row["stored_path"]
        if stored_path.exists():
            try:
                stored_path.unlink()
            except OSError:
                pass
        
        # Delete from database
        conn.execute(
            "DELETE FROM user_files WHERE id = ? AND user_id = ?",
            (file_id, user_id),
        )

