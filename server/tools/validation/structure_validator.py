"""
Structure validation engine for protein design quality assessment.

Analyzes PDB structures and produces a comprehensive validation report
including pLDDT scores (from B-factors), Ramachandran analysis, steric
clash detection, an overall quality grade (A-F), and actionable redesign
suggestions.
"""

import io
import logging
import math
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

try:
    from Bio.PDB import PDBParser, NeighborSearch, PPBuilder, is_aa
    from Bio.PDB.vectors import calc_dihedral
    HAS_BIOPYTHON = True
except ImportError:
    HAS_BIOPYTHON = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Ramachandran regions defined as (phi_min, phi_max, psi_min, psi_max) in degrees.
# Approximate boundaries following common conventions.
RAMA_REGIONS: Dict[str, Dict[str, List[Tuple[float, float, float, float]]]] = {
    "alpha_helix": {
        "favored": [(-100.0, -30.0, -67.0, -7.0)],
        "allowed": [(-120.0, -20.0, -80.0, 10.0)],
    },
    "beta_sheet": {
        "favored": [(-180.0, -100.0, 80.0, 180.0), (-180.0, -100.0, -180.0, -120.0)],
        "allowed": [(-180.0, -80.0, 60.0, 180.0), (-180.0, -80.0, -180.0, -100.0)],
    },
    "left_handed_helix": {
        "favored": [(30.0, 100.0, 7.0, 67.0)],
        "allowed": [(20.0, 120.0, -10.0, 80.0)],
    },
}

# Two non-bonded heavy atoms closer than this (Angstroms) are clashing.
CLASH_THRESHOLD: float = 2.2

# Atoms within this distance are considered covalently bonded (skip for clash).
BONDED_THRESHOLD: float = 1.9


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ResidueMetrics:
    """Per-residue quality metrics."""

    chain_id: str
    residue_number: int
    residue_name: str
    plddt: Optional[float] = None
    phi: Optional[float] = None
    psi: Optional[float] = None
    rama_region: str = "unknown"
    clashes: int = 0


@dataclass
class ValidationReport:
    """Complete structure validation report."""

    # Overall
    grade: str = "F"
    overall_score: float = 0.0

    # pLDDT metrics
    plddt_mean: float = 0.0
    plddt_median: float = 0.0
    plddt_high_confidence: int = 0  # residues with pLDDT >= 70
    plddt_low_confidence: int = 0   # residues with pLDDT < 50
    plddt_per_residue: List[Dict[str, Any]] = field(default_factory=list)

    # Ramachandran metrics
    rama_favored: int = 0
    rama_allowed: int = 0
    rama_outlier: int = 0
    rama_total: int = 0
    rama_favored_pct: float = 0.0
    rama_outlier_pct: float = 0.0
    rama_data: List[Dict[str, Any]] = field(default_factory=list)

    # Clash metrics
    clash_count: int = 0
    clash_details: List[Dict[str, Any]] = field(default_factory=list)

    # Summary
    total_residues: int = 0
    chains: List[str] = field(default_factory=list)
    suggestions: List[Dict[str, Any]] = field(default_factory=list)
    residue_metrics: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the report to a plain dictionary."""
        return asdict(self)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _in_region(
    phi: float, psi: float, bounds: List[Tuple[float, float, float, float]]
) -> bool:
    """Return True if (phi, psi) falls inside any of the rectangular *bounds*."""
    for phi_min, phi_max, psi_min, psi_max in bounds:
        if phi_min <= phi <= phi_max and psi_min <= psi <= psi_max:
            return True
    return False


def _classify_rama(phi: Optional[float], psi: Optional[float]) -> str:
    """Classify a phi/psi pair into favored / allowed / outlier."""
    if phi is None or psi is None:
        return "unknown"

    # Check favored regions first, then allowed.
    for _region_name, region_data in RAMA_REGIONS.items():
        if _in_region(phi, psi, region_data["favored"]):
            return "favored"
    for _region_name, region_data in RAMA_REGIONS.items():
        if _in_region(phi, psi, region_data["allowed"]):
            return "allowed"
    return "outlier"


def _compute_grade(score: float) -> str:
    """Map a 0-100 score to a letter grade."""
    if score >= 90:
        return "A"
    if score >= 70:
        return "B"
    if score >= 50:
        return "C"
    if score >= 30:
        return "D"
    return "F"


def _compress_residue_ranges(residue_ids: List[Tuple[str, int]]) -> str:
    """
    Compress a list of (chain, resnum) into a human-readable range string.

    Example: [("A", 10), ("A", 11), ("A", 12), ("B", 5)] -> "A:10-12, B:5"
    """
    if not residue_ids:
        return ""

    # Group by chain
    chain_groups: Dict[str, List[int]] = {}
    for chain, resnum in sorted(residue_ids):
        chain_groups.setdefault(chain, []).append(resnum)

    parts: List[str] = []
    for chain in sorted(chain_groups.keys()):
        nums = sorted(set(chain_groups[chain]))
        ranges: List[str] = []
        start = nums[0]
        end = nums[0]
        for n in nums[1:]:
            if n == end + 1:
                end = n
            else:
                ranges.append(f"{start}-{end}" if start != end else str(start))
                start = end = n
        ranges.append(f"{start}-{end}" if start != end else str(start))
        parts.append(f"{chain}:{','.join(ranges)}")

    return "; ".join(parts)


def _residues_to_dicts(
    residue_ids: List[Tuple[str, int]],
) -> List[Dict[str, Any]]:
    """Convert (chain_id, resnum) tuples to dicts for the frontend."""
    return [
        {"chain_id": chain, "residue_number": resnum}
        for chain, resnum in residue_ids
    ]


def _generate_suggestions(
    plddt_scores: List[float],
    rama_outlier_pct: float,
    clash_count: int,
    low_plddt_residues: List[Tuple[str, int]],
    rama_outlier_residues: List[Tuple[str, int]],
    clash_residues: List[Tuple[str, int]],
) -> List[Dict[str, Any]]:
    """
    Produce actionable redesign suggestions based on validation metrics.

    Each suggestion is a dict with keys:
      type, severity, message, detail, action, residues
    matching the frontend ``ValidationSuggestion`` interface.
    """
    suggestions: List[Dict[str, Any]] = []

    # --- pLDDT-based suggestions ---
    if low_plddt_residues:
        region_str = _compress_residue_ranges(low_plddt_residues)
        suggestions.append({
            "type": "confidence",
            "severity": "high",
            "message": f"Low confidence regions at [{region_str}]",
            "detail": (
                "These residues have pLDDT < 50, indicating the model is uncertain "
                "about their conformation."
            ),
            "action": "Redesign with RFdiffusion (partial diffusion)",
            "residues": _residues_to_dicts(low_plddt_residues),
        })
    if plddt_scores:
        mean_plddt = sum(plddt_scores) / len(plddt_scores)
        if mean_plddt < 50:
            suggestions.append({
                "type": "confidence",
                "severity": "critical",
                "message": "Overall pLDDT is very low (<50)",
                "detail": (
                    "The structure may need significant redesign. Try generating "
                    "a new backbone with RFdiffusion and redesigning the sequence "
                    "with ProteinMPNN."
                ),
                "action": "Generate new backbone with RFdiffusion",
                "residues": [],
            })
        elif mean_plddt < 70:
            suggestions.append({
                "type": "confidence",
                "severity": "medium",
                "message": "Mean pLDDT is moderate (<70)",
                "detail": (
                    "Running ProteinMPNN sequence design on the current backbone "
                    "may improve predicted confidence."
                ),
                "action": "Run ProteinMPNN sequence design",
                "residues": [],
            })

    # --- Ramachandran suggestions ---
    if rama_outlier_pct > 5.0:
        region_str = _compress_residue_ranges(rama_outlier_residues)
        suggestions.append({
            "type": "geometry",
            "severity": "high",
            "message": f"Ramachandran outliers ({rama_outlier_pct:.1f}%) at [{region_str}]",
            "detail": (
                "Use RFdiffusion partial diffusion on these regions to fix "
                "backbone dihedral angles, then re-run ProteinMPNN."
            ),
            "action": "Fix with RFdiffusion partial diffusion",
            "residues": _residues_to_dicts(rama_outlier_residues),
        })
    elif rama_outlier_pct > 2.0:
        suggestions.append({
            "type": "geometry",
            "severity": "medium",
            "message": f"Ramachandran outliers at {rama_outlier_pct:.1f}%",
            "detail": (
                "Minor backbone adjustments via energy minimization or short "
                "RFdiffusion refinement may resolve these."
            ),
            "action": "Apply energy minimization",
            "residues": _residues_to_dicts(rama_outlier_residues),
        })

    # --- Clash suggestions ---
    if clash_count > 10:
        region_str = _compress_residue_ranges(clash_residues)
        suggestions.append({
            "type": "clashes",
            "severity": "high",
            "message": f"Significant steric clashes ({clash_count}) near [{region_str}]",
            "detail": (
                "Run ProteinMPNN to redesign side-chains in these regions, "
                "or apply energy minimization to relieve clashes."
            ),
            "action": "Redesign side-chains with ProteinMPNN",
            "residues": _residues_to_dicts(clash_residues),
        })
    elif clash_count > 0:
        suggestions.append({
            "type": "clashes",
            "severity": "low",
            "message": f"{clash_count} steric clash(es) found",
            "detail": "A short energy minimization step should resolve these.",
            "action": "Apply energy minimization",
            "residues": _residues_to_dicts(clash_residues),
        })

    if not suggestions:
        suggestions.append({
            "type": "success",
            "severity": "low",
            "message": "Structure passes all quality checks",
            "detail": "Ready for downstream analysis or experimental validation.",
            "action": "",
            "residues": [],
        })

    return suggestions


# ---------------------------------------------------------------------------
# Main validation function
# ---------------------------------------------------------------------------

def validate_structure(pdb_content: str) -> ValidationReport:
    """
    Validate a protein structure from PDB-format text.

    Parameters
    ----------
    pdb_content : str
        The full text of a PDB file.

    Returns
    -------
    ValidationReport
        A structured report with quality metrics, grade, and suggestions.

    Raises
    ------
    RuntimeError
        If BioPython or numpy are not installed.
    ValueError
        If the PDB content is empty or cannot be parsed.
    """
    if not HAS_BIOPYTHON:
        raise RuntimeError(
            "BioPython is required for structure validation. "
            "Install it with: pip install biopython"
        )
    if not HAS_NUMPY:
        raise RuntimeError(
            "NumPy is required for structure validation. "
            "Install it with: pip install numpy"
        )

    if not pdb_content or not pdb_content.strip():
        raise ValueError("PDB content is empty.")

    # ------------------------------------------------------------------
    # Parse structure
    # ------------------------------------------------------------------
    parser = PDBParser(QUIET=True)
    try:
        structure = parser.get_structure("structure", io.StringIO(pdb_content))
    except Exception as exc:
        raise ValueError(f"Failed to parse PDB content: {exc}") from exc

    model = structure[0]  # first model

    # ------------------------------------------------------------------
    # Collect residues and extract pLDDT from B-factors of CA atoms
    # ------------------------------------------------------------------
    residue_map: Dict[Tuple[str, int], ResidueMetrics] = {}
    plddt_scores: List[float] = []
    all_atoms = []
    chain_ids: set = set()

    for chain in model:
        chain_id = chain.id
        chain_ids.add(chain_id)
        for residue in chain:
            if not is_aa(residue, standard=True):
                continue
            resnum = residue.id[1]
            resname = residue.resname.strip()

            plddt_val: Optional[float] = None
            if "CA" in residue:
                ca = residue["CA"]
                plddt_val = float(ca.get_bfactor())
                plddt_scores.append(plddt_val)

            key = (chain_id, resnum)
            residue_map[key] = ResidueMetrics(
                chain_id=chain_id,
                residue_number=resnum,
                residue_name=resname,
                plddt=plddt_val,
            )

            for atom in residue:
                all_atoms.append(atom)

    total_residues = len(residue_map)
    if total_residues == 0:
        raise ValueError(
            "No standard amino acid residues found in the PDB content."
        )

    # ------------------------------------------------------------------
    # pLDDT statistics
    # ------------------------------------------------------------------
    plddt_array = np.array(plddt_scores) if plddt_scores else np.array([0.0])
    plddt_mean = float(np.mean(plddt_array))
    plddt_median = float(np.median(plddt_array))
    plddt_high = int(np.sum(plddt_array >= 70))
    plddt_low = int(np.sum(plddt_array < 50))

    low_plddt_residues: List[Tuple[str, int]] = [
        (rm.chain_id, rm.residue_number)
        for rm in residue_map.values()
        if rm.plddt is not None and rm.plddt < 50
    ]

    plddt_per_residue = [
        {
            "chain_id": rm.chain_id,
            "residue_number": rm.residue_number,
            "residue_name": rm.residue_name,
            "plddt": rm.plddt,
        }
        for rm in residue_map.values()
    ]

    # ------------------------------------------------------------------
    # Ramachandran analysis via PPBuilder
    # ------------------------------------------------------------------
    ppb = PPBuilder()
    rama_favored = 0
    rama_allowed = 0
    rama_outlier = 0
    rama_total = 0
    rama_data: List[Dict[str, Any]] = []
    rama_outlier_residues: List[Tuple[str, int]] = []

    for pp in ppb.build_peptides(model):
        phi_psi_list = pp.get_phi_psi_list()
        residues_in_pp = list(pp)
        for residue, (phi_raw, psi_raw) in zip(residues_in_pp, phi_psi_list):
            chain_id = residue.get_parent().id
            resnum = residue.id[1]
            key = (chain_id, resnum)

            phi_deg = math.degrees(phi_raw) if phi_raw is not None else None
            psi_deg = math.degrees(psi_raw) if psi_raw is not None else None

            classification = _classify_rama(phi_deg, psi_deg)

            if key in residue_map:
                residue_map[key].phi = phi_deg
                residue_map[key].psi = psi_deg
                residue_map[key].rama_region = classification

            if classification == "unknown":
                # Terminal residues with missing phi or psi -- skip counting
                continue

            rama_total += 1
            if classification == "favored":
                rama_favored += 1
            elif classification == "allowed":
                rama_allowed += 1
            else:
                rama_outlier += 1
                rama_outlier_residues.append((chain_id, resnum))

            rama_data.append(
                {
                    "chain_id": chain_id,
                    "residue_number": resnum,
                    "residue_name": residue.resname.strip(),
                    "phi": phi_deg,
                    "psi": psi_deg,
                    "region": classification,
                }
            )

    rama_favored_pct = (rama_favored / rama_total * 100) if rama_total > 0 else 0.0
    rama_outlier_pct = (rama_outlier / rama_total * 100) if rama_total > 0 else 0.0

    # ------------------------------------------------------------------
    # Steric clash detection via NeighborSearch
    # ------------------------------------------------------------------
    clash_count = 0
    clash_details: List[Dict[str, Any]] = []
    clash_residue_set: set = set()

    if all_atoms:
        ns = NeighborSearch(all_atoms)
        close_pairs = ns.search_all(CLASH_THRESHOLD, level="A")

        seen_pairs: set = set()
        for atom_a, atom_b in close_pairs:
            res_a = atom_a.get_parent()
            res_b = atom_b.get_parent()

            # Skip if same residue
            if res_a.get_full_id() == res_b.get_full_id():
                continue

            # Skip hydrogen atoms (if present)
            if atom_a.element == "H" or atom_b.element == "H":
                continue

            # Skip non-standard residues
            if not is_aa(res_a, standard=True) or not is_aa(res_b, standard=True):
                continue

            # Determine distance
            dist = float(atom_a - atom_b)

            # Skip bonded-distance contacts (peptide bonds, etc.)
            if dist < BONDED_THRESHOLD:
                # Could be a covalent bond -- check if residues are sequential
                chain_a = res_a.get_parent().id
                chain_b = res_b.get_parent().id
                resnum_a = res_a.id[1]
                resnum_b = res_b.id[1]
                if chain_a == chain_b and abs(resnum_a - resnum_b) <= 1:
                    continue

            # Deduplicate
            pair_key = tuple(sorted([atom_a.get_full_id(), atom_b.get_full_id()]))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            clash_count += 1
            chain_a = res_a.get_parent().id
            chain_b = res_b.get_parent().id
            resnum_a = res_a.id[1]
            resnum_b = res_b.id[1]
            clash_residue_set.add((chain_a, resnum_a))
            clash_residue_set.add((chain_b, resnum_b))

            clash_details.append(
                {
                    "atom1": f"{chain_a}:{res_a.resname.strip()}{resnum_a}:{atom_a.name}",
                    "atom2": f"{chain_b}:{res_b.resname.strip()}{resnum_b}:{atom_b.name}",
                    "distance": round(dist, 2),
                }
            )

    clash_residues = sorted(clash_residue_set)

    # ------------------------------------------------------------------
    # Overall score (weighted composite)
    # ------------------------------------------------------------------
    # pLDDT component: direct mapping 0-100 -> 0-100
    plddt_component = min(plddt_mean, 100.0)

    # Ramachandran component: favored% maps to score
    rama_component = rama_favored_pct  # 0-100

    # Clash component: fewer clashes = higher score
    # 0 clashes -> 100, 20+ clashes -> 0
    max_clashes_for_zero = 20
    clash_component = max(0.0, 100.0 - (clash_count / max_clashes_for_zero) * 100.0)

    overall_score = (
        0.50 * plddt_component
        + 0.30 * rama_component
        + 0.20 * clash_component
    )
    overall_score = round(min(overall_score, 100.0), 1)
    grade = _compute_grade(overall_score)

    # ------------------------------------------------------------------
    # Suggestions
    # ------------------------------------------------------------------
    suggestions = _generate_suggestions(
        plddt_scores=plddt_scores,
        rama_outlier_pct=rama_outlier_pct,
        clash_count=clash_count,
        low_plddt_residues=low_plddt_residues,
        rama_outlier_residues=rama_outlier_residues,
        clash_residues=clash_residues,
    )

    # ------------------------------------------------------------------
    # Build residue_metrics list
    # ------------------------------------------------------------------
    # Update per-residue clash counts first
    for chain_id, resnum in clash_residues:
        key = (chain_id, resnum)
        if key in residue_map:
            residue_map[key].clashes += 1
    # Rebuild after clash count update
    residue_metrics_list = [
        {
            "chain_id": rm.chain_id,
            "residue_number": rm.residue_number,
            "residue_name": rm.residue_name,
            "plddt": rm.plddt,
            "phi": rm.phi,
            "psi": rm.psi,
            "rama_region": rm.rama_region,
            "clashes": rm.clashes,
        }
        for rm in residue_map.values()
    ]

    # ------------------------------------------------------------------
    # Assemble report
    # ------------------------------------------------------------------
    report = ValidationReport(
        grade=grade,
        overall_score=overall_score,
        plddt_mean=round(plddt_mean, 2),
        plddt_median=round(plddt_median, 2),
        plddt_high_confidence=plddt_high,
        plddt_low_confidence=plddt_low,
        plddt_per_residue=plddt_per_residue,
        rama_favored=rama_favored,
        rama_allowed=rama_allowed,
        rama_outlier=rama_outlier,
        rama_total=rama_total,
        rama_favored_pct=round(rama_favored_pct, 1),
        rama_outlier_pct=round(rama_outlier_pct, 1),
        rama_data=rama_data,
        clash_count=clash_count,
        clash_details=clash_details,
        total_residues=total_residues,
        chains=sorted(chain_ids),
        suggestions=suggestions,
        residue_metrics=residue_metrics_list,
    )

    logger.info(
        "Validation complete: grade=%s, score=%.1f, residues=%d, "
        "pLDDT_mean=%.1f, rama_fav=%.1f%%, clashes=%d",
        grade,
        overall_score,
        total_residues,
        plddt_mean,
        rama_favored_pct,
        clash_count,
    )

    return report
