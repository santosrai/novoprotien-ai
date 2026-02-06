# Protein Design Validation System - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an on-demand structure validation system that gives researchers quality metrics (pLDDT, Ramachandran, clashes, RMSD comparison) with actionable redesign suggestions, accessible via both chat and pipeline canvas.

**Architecture:** A new `validation-agent` handles chat-triggered validation requests, delegating to a Python `structure_validator.py` that uses BioPython for geometric analysis and pLDDT parsing. The frontend renders results via a `ValidationPanel.tsx` component with Recharts-based plots (Ramachandran, PAE heatmap, confidence bar chart). A `validation_node` in the pipeline canvas enables automated workflows. MolStar gets a new `colorByConfidence` method for per-residue pLDDT coloring.

**Tech Stack:** Python (BioPython, numpy), React + TypeScript, Recharts (new dep), MolStar API, FastAPI endpoints, Zustand store, TailwindCSS.

---

## Task 1: Install Dependencies

**Files:**
- Modify: `package.json` (add recharts)
- Modify: `server/requirements.txt` (add biopython, numpy)

**Step 1: Add recharts to frontend**

```bash
cd "/Users/alizabista/.claude-worktrees/novoprotien-ai-main 2/strange-keller"
npm install recharts
```

**Step 2: Add BioPython and numpy to server requirements**

Add to `server/requirements.txt`:
```
biopython>=1.83
numpy>=1.26.0
```

**Step 3: Install Python deps**

```bash
cd "/Users/alizabista/.claude-worktrees/novoprotien-ai-main 2/strange-keller/server"
source venv/bin/activate
pip install biopython numpy
```

**Step 4: Commit**

```bash
cd "/Users/alizabista/.claude-worktrees/novoprotien-ai-main 2/strange-keller"
git add package.json package-lock.json server/requirements.txt
git commit -m "chore: add recharts, biopython, numpy dependencies for validation system"
```

---

## Task 2: Backend - Structure Validator Core (`structure_validator.py`)

This is the core analysis engine. It takes PDB content (string) and returns a structured validation report with pLDDT scores, Ramachandran angles, clash detection, and an overall quality grade.

**Files:**
- Create: `server/tools/validation/__init__.py`
- Create: `server/tools/validation/structure_validator.py`

**Step 1: Create the validation tools package**

Create `server/tools/validation/__init__.py`:
```python
"""Structure validation tools for protein design quality assessment."""
```

**Step 2: Write structure_validator.py**

Create `server/tools/validation/structure_validator.py`:

```python
"""
Protein structure validation engine.
Analyzes PDB structures for quality metrics: pLDDT confidence, Ramachandran geometry,
steric clashes, and generates actionable redesign suggestions.
"""

import io
import logging
import math
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from Bio.PDB import PDBParser, NeighborSearch
    from Bio.PDB.Polypeptide import PPBuilder, is_aa
    from Bio.PDB.vectors import calc_dihedral
    import numpy as np
    HAS_BIOPYTHON = True
except ImportError:
    HAS_BIOPYTHON = False
    logger.warning("BioPython not installed. Structure validation unavailable.")


# Ramachandran region definitions (degrees)
RAMA_REGIONS = {
    "favored": [
        # Alpha helix
        {"phi": (-120, -20), "psi": (-80, 20)},
        # Beta sheet
        {"phi": (-180, -100), "psi": (80, 180)},
        {"phi": (-180, -100), "psi": (-180, -120)},
        # Left-handed helix (rare but allowed)
        {"phi": (20, 100), "psi": (20, 100)},
    ],
    "allowed": [
        {"phi": (-180, 0), "psi": (-180, 180)},
        {"phi": (0, 180), "psi": (-180, 180)},
    ],
}

# Clash distance threshold (Angstroms) - atoms closer than this are clashing
CLASH_THRESHOLD = 2.2
# Bonded atom distance (skip clashes between bonded atoms)
BONDED_THRESHOLD = 1.9


@dataclass
class ResidueMetrics:
    chain_id: str
    residue_number: int
    residue_name: str
    plddt: Optional[float] = None
    phi: Optional[float] = None
    psi: Optional[float] = None
    rama_region: str = "unknown"  # "favored", "allowed", "outlier"
    clashes: int = 0


@dataclass
class ValidationReport:
    # Overall grade: A (>90), B (70-90), C (50-70), D (30-50), F (<30)
    grade: str = "N/A"
    overall_score: float = 0.0

    # pLDDT metrics
    plddt_mean: float = 0.0
    plddt_median: float = 0.0
    plddt_high_confidence: int = 0  # residues with pLDDT >= 70
    plddt_low_confidence: int = 0   # residues with pLDDT < 50
    plddt_per_residue: List[Dict] = field(default_factory=list)

    # Ramachandran metrics
    rama_favored: int = 0
    rama_allowed: int = 0
    rama_outlier: int = 0
    rama_total: int = 0
    rama_favored_pct: float = 0.0
    rama_outlier_pct: float = 0.0
    rama_data: List[Dict] = field(default_factory=list)  # [{phi, psi, residue, region}]

    # Clash metrics
    clash_count: int = 0
    clash_details: List[Dict] = field(default_factory=list)

    # Summary
    total_residues: int = 0
    chains: List[str] = field(default_factory=list)
    suggestions: List[Dict] = field(default_factory=list)

    # Per-residue data for frontend
    residue_metrics: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)


def _in_region(phi: float, psi: float, regions: List[Dict]) -> bool:
    """Check if phi/psi angles fall within any of the defined regions."""
    for region in regions:
        phi_range = region["phi"]
        psi_range = region["psi"]
        if phi_range[0] <= phi <= phi_range[1] and psi_range[0] <= psi <= psi_range[1]:
            return True
    return False


def _classify_rama(phi: float, psi: float) -> str:
    """Classify a residue's Ramachandran region."""
    if _in_region(phi, psi, RAMA_REGIONS["favored"]):
        return "favored"
    elif _in_region(phi, psi, RAMA_REGIONS["allowed"]):
        return "allowed"
    return "outlier"


def _compute_grade(score: float) -> str:
    """Convert numeric score (0-100) to letter grade."""
    if score >= 90:
        return "A"
    elif score >= 70:
        return "B"
    elif score >= 50:
        return "C"
    elif score >= 30:
        return "D"
    return "F"


def _generate_suggestions(report: ValidationReport) -> List[Dict]:
    """Generate actionable redesign suggestions based on validation results."""
    suggestions = []

    # pLDDT-based suggestions
    if report.plddt_low_confidence > 0:
        low_residues = [
            r for r in report.plddt_per_residue
            if r.get("plddt", 100) < 50
        ]
        residue_ranges = _compress_residue_ranges(low_residues)
        suggestions.append({
            "type": "confidence",
            "severity": "high" if report.plddt_low_confidence > report.total_residues * 0.2 else "medium",
            "message": f"{report.plddt_low_confidence} residues have low confidence (pLDDT < 50)",
            "detail": f"Regions: {residue_ranges}",
            "action": "Consider constraining these loop regions in RFdiffusion or fixing positions in ProteinMPNN",
            "residues": low_residues,
        })

    # Ramachandran suggestions
    if report.rama_outlier_pct > 5.0:
        outlier_residues = [
            r for r in report.rama_data if r.get("region") == "outlier"
        ]
        suggestions.append({
            "type": "geometry",
            "severity": "high" if report.rama_outlier_pct > 10 else "medium",
            "message": f"{report.rama_outlier} Ramachandran outliers ({report.rama_outlier_pct:.1f}%)",
            "detail": "These residues have unusual backbone geometry",
            "action": "Try ProteinMPNN with fixed positions at these residues, or increase AlphaFold relax steps",
            "residues": outlier_residues[:10],  # Limit to top 10
        })

    # Clash suggestions
    if report.clash_count > 0:
        suggestions.append({
            "type": "clashes",
            "severity": "high" if report.clash_count > 10 else "medium",
            "message": f"{report.clash_count} steric clashes detected",
            "detail": "Atoms are too close together, indicating structural strain",
            "action": "Enable relaxation in AlphaFold2 (num_relax > 0) or run energy minimization",
            "residues": report.clash_details[:10],
        })

    # Good structure
    if not suggestions:
        suggestions.append({
            "type": "success",
            "severity": "low",
            "message": "Structure passes all quality checks",
            "detail": f"Grade {report.grade} with {report.plddt_mean:.1f} mean pLDDT",
            "action": "Structure is ready for downstream analysis or experimental validation",
            "residues": [],
        })

    return suggestions


def _compress_residue_ranges(residues: List[Dict]) -> str:
    """Compress residue list into ranges like 'A:45-52, A:78-85'."""
    if not residues:
        return "none"

    groups: Dict[str, List[int]] = {}
    for r in residues:
        chain = r.get("chain_id", "?")
        resnum = r.get("residue_number", 0)
        groups.setdefault(chain, []).append(resnum)

    parts = []
    for chain, nums in sorted(groups.items()):
        nums.sort()
        ranges = []
        start = nums[0]
        end = nums[0]
        for n in nums[1:]:
            if n == end + 1:
                end = n
            else:
                ranges.append(f"{chain}:{start}-{end}" if start != end else f"{chain}:{start}")
                start = end = n
        ranges.append(f"{chain}:{start}-{end}" if start != end else f"{chain}:{start}")
        parts.extend(ranges)

    return ", ".join(parts[:5]) + ("..." if len(parts) > 5 else "")


def validate_structure(pdb_content: str) -> ValidationReport:
    """
    Run full validation on a PDB structure string.

    Args:
        pdb_content: PDB file content as string

    Returns:
        ValidationReport with all quality metrics
    """
    if not HAS_BIOPYTHON:
        report = ValidationReport()
        report.grade = "N/A"
        report.suggestions = [{
            "type": "error",
            "severity": "high",
            "message": "BioPython not installed - validation unavailable",
            "detail": "Install with: pip install biopython numpy",
            "action": "Install dependencies and restart server",
            "residues": [],
        }]
        return report

    report = ValidationReport()

    try:
        parser = PDBParser(QUIET=True)
        structure = parser.get_structure("query", io.StringIO(pdb_content))
        model = structure[0]

        # Collect all residues
        all_residues: List[ResidueMetrics] = []
        chain_ids = []

        for chain in model:
            chain_id = chain.id
            chain_ids.append(chain_id)

            for residue in chain:
                if not is_aa(residue, standard=True):
                    continue

                resnum = residue.id[1]
                resname = residue.resname

                # Extract pLDDT from B-factor (AlphaFold stores pLDDT in B-factor column)
                plddt = None
                if "CA" in residue:
                    plddt = residue["CA"].bfactor

                all_residues.append(ResidueMetrics(
                    chain_id=chain_id,
                    residue_number=resnum,
                    residue_name=resname,
                    plddt=plddt,
                ))

        report.total_residues = len(all_residues)
        report.chains = chain_ids

        # === pLDDT Analysis ===
        plddt_values = [r.plddt for r in all_residues if r.plddt is not None]
        if plddt_values:
            arr = np.array(plddt_values)
            report.plddt_mean = float(np.mean(arr))
            report.plddt_median = float(np.median(arr))
            report.plddt_high_confidence = int(np.sum(arr >= 70))
            report.plddt_low_confidence = int(np.sum(arr < 50))
            report.plddt_per_residue = [
                {
                    "chain_id": r.chain_id,
                    "residue_number": r.residue_number,
                    "residue_name": r.residue_name,
                    "plddt": r.plddt,
                }
                for r in all_residues if r.plddt is not None
            ]

        # === Ramachandran Analysis ===
        ppb = PPBuilder()
        for pp in ppb.build_peptides(model):
            phi_psi_list = pp.get_phi_psi_list()
            residues_in_pp = list(pp)

            for i, (phi, psi) in enumerate(phi_psi_list):
                if phi is None or psi is None:
                    continue

                phi_deg = math.degrees(phi)
                psi_deg = math.degrees(psi)
                region = _classify_rama(phi_deg, psi_deg)

                res = residues_in_pp[i]
                chain_id = res.get_parent().id
                resnum = res.id[1]
                resname = res.resname

                report.rama_data.append({
                    "phi": round(phi_deg, 1),
                    "psi": round(psi_deg, 1),
                    "chain_id": chain_id,
                    "residue_number": resnum,
                    "residue_name": resname,
                    "region": region,
                })

                if region == "favored":
                    report.rama_favored += 1
                elif region == "allowed":
                    report.rama_allowed += 1
                else:
                    report.rama_outlier += 1

                # Update per-residue metrics
                for r in all_residues:
                    if r.chain_id == chain_id and r.residue_number == resnum:
                        r.phi = phi_deg
                        r.psi = psi_deg
                        r.rama_region = region
                        break

        report.rama_total = report.rama_favored + report.rama_allowed + report.rama_outlier
        if report.rama_total > 0:
            report.rama_favored_pct = round(100.0 * report.rama_favored / report.rama_total, 1)
            report.rama_outlier_pct = round(100.0 * report.rama_outlier / report.rama_total, 1)

        # === Clash Detection ===
        atoms = [atom for atom in model.get_atoms()]
        if len(atoms) > 1:
            ns = NeighborSearch(atoms)
            seen_pairs = set()
            for atom in atoms:
                close_atoms = ns.search(atom.coord, CLASH_THRESHOLD)
                for other in close_atoms:
                    if atom is other:
                        continue
                    # Skip bonded atoms (same residue)
                    if atom.get_parent() is other.get_parent():
                        continue
                    # Skip already-seen pairs
                    pair_key = tuple(sorted([atom.serial_number, other.serial_number]))
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    dist = atom - other
                    if dist < CLASH_THRESHOLD and dist > 0.5:
                        res1 = atom.get_parent()
                        res2 = other.get_parent()
                        report.clash_details.append({
                            "atom1": f"{res1.get_parent().id}:{res1.id[1]}{res1.resname}.{atom.name}",
                            "atom2": f"{res2.get_parent().id}:{res2.id[1]}{res2.resname}.{other.name}",
                            "distance": round(float(dist), 2),
                        })

            report.clash_count = len(report.clash_details)

        # === Overall Score ===
        # Weighted scoring: 50% pLDDT, 30% Ramachandran, 20% clashes
        plddt_score = report.plddt_mean if plddt_values else 50.0

        rama_score = 100.0
        if report.rama_total > 0:
            rama_score = (report.rama_favored_pct * 1.0) + ((100 - report.rama_favored_pct - report.rama_outlier_pct) * 0.5)

        clash_score = 100.0
        if report.total_residues > 0:
            clash_ratio = report.clash_count / report.total_residues
            clash_score = max(0, 100 - clash_ratio * 500)

        report.overall_score = round(0.5 * plddt_score + 0.3 * rama_score + 0.2 * clash_score, 1)
        report.grade = _compute_grade(report.overall_score)

        # === Per-residue metrics for frontend ===
        report.residue_metrics = [
            {
                "chain_id": r.chain_id,
                "residue_number": r.residue_number,
                "residue_name": r.residue_name,
                "plddt": r.plddt,
                "phi": round(r.phi, 1) if r.phi is not None else None,
                "psi": round(r.psi, 1) if r.psi is not None else None,
                "rama_region": r.rama_region,
                "clashes": r.clashes,
            }
            for r in all_residues
        ]

        # === Generate Suggestions ===
        report.suggestions = _generate_suggestions(report)

    except Exception as e:
        logger.error(f"Validation failed: {e}", exc_info=True)
        report.grade = "ERR"
        report.suggestions = [{
            "type": "error",
            "severity": "critical",
            "message": f"Validation failed: {str(e)}",
            "detail": "The PDB file may be malformed or missing required data",
            "action": "Check PDB format and try again",
            "residues": [],
        }]

    return report
```

**Step 3: Verify the module imports correctly**

```bash
cd "/Users/alizabista/.claude-worktrees/novoprotien-ai-main 2/strange-keller/server"
source venv/bin/activate
python -c "from tools.validation.structure_validator import validate_structure, ValidationReport; print('OK')"
```

Expected: `OK`

**Step 4: Commit**

```bash
cd "/Users/alizabista/.claude-worktrees/novoprotien-ai-main 2/strange-keller"
git add server/tools/validation/
git commit -m "feat: add structure validation engine with pLDDT, Ramachandran, and clash analysis"
```

---

## Task 3: Backend - Validation Handler & Agent Registration

Wire the validator into the agent system so it can be triggered via chat. Follow the exact same handler pattern as `alphafold.py`.

**Files:**
- Create: `server/agents/handlers/validation.py`
- Create: `server/agents/prompts/validation.py`
- Modify: `server/agents/registry.py` (add validation-agent)
- Modify: `server/agents/runner.py` (add handler dispatch)
- Modify: `server/agents/router.py` (add routing rules)

**Step 1: Create the validation agent prompt**

Create `server/agents/prompts/validation.py`:

```python
"""System prompt for the validation agent."""

VALIDATION_AGENT_SYSTEM_PROMPT = """You are a protein structure validation expert.
You analyze protein structures and provide quality assessments.

When a user asks to validate, assess, or check a structure, you trigger the validation pipeline.

You respond with JSON containing the action to take.

Output format (JSON only):
{
  "action": "validate_structure",
  "source": "current" | "file" | "pdb_id",
  "pdb_id": "optional PDB ID",
  "file_id": "optional file ID",
  "message": "brief description of what will be validated"
}

If the user asks to compare two structures, output:
{
  "action": "compare_structures",
  "source1": "pdb_id or file_id",
  "source2": "pdb_id or file_id",
  "message": "brief description of comparison"
}
"""
```

**Step 2: Create the validation handler**

Create `server/agents/handlers/validation.py`:

```python
"""
Validation handler for protein structure quality assessment.
Follows the same pattern as alphafold.py handler.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    from ...tools.validation.structure_validator import validate_structure
    from ...domain.storage.file_access import get_user_file_path
except ImportError:
    from tools.validation.structure_validator import validate_structure
    from domain.storage.file_access import get_user_file_path


class ValidationHandler:
    """Handles structure validation requests."""

    def __init__(self):
        self.job_results: Dict[str, Any] = {}

    async def process_validation_request(
        self,
        input_text: str,
        context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Process a validation request from chat.

        The context may contain:
        - current_pdb_content: PDB string from the current viewer
        - uploaded_file_context: info about an uploaded file
        - file_id: specific file to validate
        - session_id: current chat session
        - user_id: current user
        """
        context = context or {}
        pdb_content = None
        source_label = "unknown"

        # Priority 1: Explicit file_id in context
        file_id = context.get("file_id")
        user_id = context.get("user_id")
        if file_id and user_id:
            try:
                file_path = get_user_file_path(file_id, user_id)
                if file_path and Path(file_path).exists():
                    pdb_content = Path(file_path).read_text()
                    source_label = f"file:{file_id}"
            except Exception as e:
                logger.warning(f"Could not read file {file_id}: {e}")

        # Priority 2: Current PDB content from viewer
        if not pdb_content:
            pdb_content = context.get("current_pdb_content")
            if pdb_content:
                source_label = "current viewer structure"

        # Priority 3: Uploaded file
        if not pdb_content:
            uploaded = context.get("uploaded_file_context")
            if uploaded and uploaded.get("file_id"):
                try:
                    file_path = get_user_file_path(uploaded["file_id"], user_id or "anonymous")
                    if file_path and Path(file_path).exists():
                        pdb_content = Path(file_path).read_text()
                        source_label = f"uploaded:{uploaded.get('filename', 'file')}"
                except Exception as e:
                    logger.warning(f"Could not read uploaded file: {e}")

        if not pdb_content:
            return {
                "action": "error",
                "error": "No structure available to validate. Load a structure in the viewer first, or specify a PDB file.",
                "suggestions": [
                    "Load a structure with 'show PDB:1ABC'",
                    "Upload a PDB file first",
                    "Run AlphaFold2 to predict a structure, then validate",
                ],
            }

        # Run validation
        try:
            report = validate_structure(pdb_content)
            result = report.to_dict()
            result["action"] = "validation_result"
            result["source"] = source_label

            # Store for potential re-access
            job_id = f"val_{context.get('session_id', 'unknown')}_{len(self.job_results)}"
            self.job_results[job_id] = result

            logger.info(f"Validation complete: grade={report.grade}, score={report.overall_score}")
            return result

        except Exception as e:
            logger.error(f"Validation failed: {e}", exc_info=True)
            return {
                "action": "error",
                "error": f"Validation failed: {str(e)}",
            }


validation_handler = ValidationHandler()
```

**Step 3: Register the agent in registry.py**

Add to `server/agents/registry.py` - add import at top and entry in agents dict.

At the top, add:
```python
from .prompts.validation import VALIDATION_AGENT_SYSTEM_PROMPT
```

In the `agents` dict, add after the `pipeline-agent` entry:
```python
    "validation-agent": {
        "id": "validation-agent",
        "name": "Structure Validation",
        "description": "Validates protein structure quality with pLDDT confidence scores, Ramachandran geometry analysis, steric clash detection, and provides actionable redesign suggestions. Use for: validate, check quality, assess structure, quality report, confidence score, Ramachandran, clashes.",
        "system": VALIDATION_AGENT_SYSTEM_PROMPT,
        "modelEnv": "CLAUDE_CHAT_MODEL",
        "defaultModel": os.getenv("CLAUDE_CHAT_MODEL", "claude-3-5-sonnet-20241022"),
        "kind": "validation",
        "category": "analysis",
    },
```

**Step 4: Add handler dispatch in runner.py**

In `server/agents/runner.py`, add after the ProteinMPNN handler block (around line 850):

```python
    # Special handling for Validation agent - use handler
    if agent.get("id") == "validation-agent":
        try:
            from .handlers.validation import validation_handler
            result = await validation_handler.process_validation_request(
                user_text,
                context={
                    "current_pdb_content": current_pdb_content,
                    "uploaded_file_context": uploaded_file_context,
                    "file_id": file_id,
                    "session_id": session_id,
                    "user_id": user_id,
                },
            )
            if result.get("action") == "error":
                return {"type": "text", "text": json.dumps(result)}
            return {"type": "text", "text": json.dumps(result)}
        except Exception as e:
            log_line("agent:validation:failed", {"error": str(e), "userText": user_text})
            return {"type": "text", "text": f"Validation failed: {str(e)}"}
```

Note: The `current_pdb_content` variable needs to be passed through context. Check how `current_code` is passed in the existing `run_agent` function and follow the same pattern to pass `current_pdb_content`. If it doesn't exist yet, we'll add a `pdb_content` field to the request in Task 5.

**Step 5: Add routing rules in router.py**

In `server/agents/router.py`, inside the `ainvoke` method, add a rule block before the semantic routing (after the existing keyword blocks):

```python
        # Validation agent keywords
        validation_keywords = ["validate", "validation", "quality", "check quality", "assess", "plddt", "ramachandran", "clashes", "quality report", "check structure"]
        if any(k in low for k in validation_keywords):
            return {"routedAgentId": "validation-agent", "reason": "rule:validation-keywords"}
```

**Step 6: Commit**

```bash
cd "/Users/alizabista/.claude-worktrees/novoprotien-ai-main 2/strange-keller"
git add server/agents/handlers/validation.py server/agents/prompts/validation.py server/agents/registry.py server/agents/runner.py server/agents/router.py
git commit -m "feat: add validation agent with handler, routing, and registry integration"
```

---

## Task 4: Backend - Validation API Endpoints

Add FastAPI endpoints for validation, following the same pattern as AlphaFold endpoints.

**Files:**
- Modify: `server/app.py` (add validation endpoints)

**Step 1: Add validation endpoints to app.py**

Add these endpoints after the existing ProteinMPNN or OpenFold2 endpoint blocks:

```python
# ── Validation Endpoints ─────────────────────────────────────────

@app.post("/api/validation/validate")
async def validate_structure_endpoint(request: Request, user: Dict = Depends(get_current_user)):
    """Validate a PDB structure and return quality metrics."""
    from agents.handlers.validation import validation_handler

    body = await request.json()
    pdb_content = body.get("pdb_content")
    file_id = body.get("file_id")
    user_id = user.get("id", "anonymous") if user else "anonymous"
    session_id = body.get("session_id")

    result = await validation_handler.process_validation_request(
        input_text="validate structure",
        context={
            "current_pdb_content": pdb_content,
            "file_id": file_id,
            "user_id": user_id,
            "session_id": session_id,
        },
    )

    if result.get("action") == "error":
        return JSONResponse(status_code=400, content=result)

    return JSONResponse(status_code=200, content=result)
```

**Step 2: Verify the endpoint registers**

```bash
cd "/Users/alizabista/.claude-worktrees/novoprotien-ai-main 2/strange-keller/server"
source venv/bin/activate
python -c "from app import app; routes = [r.path for r in app.routes]; assert '/api/validation/validate' in routes; print('Endpoint registered OK')"
```

**Step 3: Commit**

```bash
cd "/Users/alizabista/.claude-worktrees/novoprotien-ai-main 2/strange-keller"
git add server/app.py
git commit -m "feat: add /api/validation/validate endpoint"
```

---

## Task 5: Frontend - Validation Types & API Utility

Define TypeScript types for the validation report and add API call functions.

**Files:**
- Create: `src/types/validation.ts`
- Modify: `src/utils/api.ts` (add validation API calls)

**Step 1: Create validation types**

Create `src/types/validation.ts`:

```typescript
export interface ValidationReport {
  action: 'validation_result';
  source: string;
  grade: string;
  overall_score: number;

  // pLDDT metrics
  plddt_mean: number;
  plddt_median: number;
  plddt_high_confidence: number;
  plddt_low_confidence: number;
  plddt_per_residue: ResidueConfidence[];

  // Ramachandran
  rama_favored: number;
  rama_allowed: number;
  rama_outlier: number;
  rama_total: number;
  rama_favored_pct: number;
  rama_outlier_pct: number;
  rama_data: RamachandranPoint[];

  // Clashes
  clash_count: number;
  clash_details: ClashDetail[];

  // Summary
  total_residues: number;
  chains: string[];
  suggestions: ValidationSuggestion[];
  residue_metrics: ResidueMetric[];
}

export interface ResidueConfidence {
  chain_id: string;
  residue_number: number;
  residue_name: string;
  plddt: number;
}

export interface RamachandranPoint {
  phi: number;
  psi: number;
  chain_id: string;
  residue_number: number;
  residue_name: string;
  region: 'favored' | 'allowed' | 'outlier';
}

export interface ClashDetail {
  atom1: string;
  atom2: string;
  distance: number;
}

export interface ResidueMetric {
  chain_id: string;
  residue_number: number;
  residue_name: string;
  plddt: number | null;
  phi: number | null;
  psi: number | null;
  rama_region: string;
  clashes: number;
}

export interface ValidationSuggestion {
  type: 'confidence' | 'geometry' | 'clashes' | 'success' | 'error';
  severity: 'low' | 'medium' | 'high' | 'critical';
  message: string;
  detail: string;
  action: string;
  residues: Record<string, any>[];
}
```

**Step 2: Add validation API function to api.ts**

Add to `src/utils/api.ts`:

```typescript
import type { ValidationReport } from '../types/validation';

export async function validateStructure(
  pdbContent?: string,
  fileId?: string,
  sessionId?: string,
): Promise<ValidationReport> {
  const response = await api.post('/validation/validate', {
    pdb_content: pdbContent,
    file_id: fileId,
    session_id: sessionId,
  });
  return response.data;
}
```

**Step 3: Commit**

```bash
cd "/Users/alizabista/.claude-worktrees/novoprotien-ai-main 2/strange-keller"
git add src/types/validation.ts src/utils/api.ts
git commit -m "feat: add validation TypeScript types and API utility"
```

---

## Task 6: Frontend - ValidationPanel Component

The main UI component that renders the full validation report. It includes:
- Overall grade badge
- pLDDT bar chart (per-residue)
- Ramachandran scatter plot
- Clash summary
- Actionable suggestion cards

**Files:**
- Create: `src/components/ValidationPanel.tsx`

**Step 1: Create ValidationPanel.tsx**

Create `src/components/ValidationPanel.tsx`:

```typescript
import React, { useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ScatterChart, Scatter, Cell, ReferenceLine,
} from 'recharts';
import {
  Shield, ChevronDown, ChevronUp, AlertTriangle, CheckCircle,
  XCircle, Info, Zap,
} from 'lucide-react';
import type { ValidationReport, ValidationSuggestion } from '../types/validation';

interface ValidationPanelProps {
  report: ValidationReport;
  onColorByConfidence?: () => void;
  onFocusResidues?: (residues: { chain_id: string; residue_number: number }[]) => void;
}

const GRADE_COLORS: Record<string, string> = {
  A: 'text-green-600 bg-green-50 border-green-200',
  B: 'text-blue-600 bg-blue-50 border-blue-200',
  C: 'text-yellow-600 bg-yellow-50 border-yellow-200',
  D: 'text-orange-600 bg-orange-50 border-orange-200',
  F: 'text-red-600 bg-red-50 border-red-200',
  'N/A': 'text-gray-500 bg-gray-50 border-gray-200',
  ERR: 'text-red-600 bg-red-50 border-red-200',
};

const PLDDT_COLORS = {
  veryHigh: '#0053d6',  // >= 90
  high: '#65cbf3',       // 70-90
  low: '#ffdb13',        // 50-70
  veryLow: '#ff7d45',    // < 50
};

function plddtColor(val: number): string {
  if (val >= 90) return PLDDT_COLORS.veryHigh;
  if (val >= 70) return PLDDT_COLORS.high;
  if (val >= 50) return PLDDT_COLORS.low;
  return PLDDT_COLORS.veryLow;
}

function ramaColor(region: string): string {
  if (region === 'favored') return '#22c55e';
  if (region === 'allowed') return '#eab308';
  return '#ef4444';
}

function SuggestionCard({ suggestion }: { suggestion: ValidationSuggestion }) {
  const icons: Record<string, React.ReactNode> = {
    confidence: <AlertTriangle className="w-4 h-4 text-amber-500" />,
    geometry: <XCircle className="w-4 h-4 text-red-500" />,
    clashes: <Zap className="w-4 h-4 text-orange-500" />,
    success: <CheckCircle className="w-4 h-4 text-green-500" />,
    error: <XCircle className="w-4 h-4 text-red-500" />,
  };

  const borderColors: Record<string, string> = {
    low: 'border-green-200',
    medium: 'border-yellow-200',
    high: 'border-orange-200',
    critical: 'border-red-200',
  };

  return (
    <div className={`p-3 rounded-lg border ${borderColors[suggestion.severity] || 'border-gray-200'} bg-white`}>
      <div className="flex items-start gap-2">
        {icons[suggestion.type] || <Info className="w-4 h-4 text-gray-400" />}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-900">{suggestion.message}</p>
          <p className="text-xs text-gray-500 mt-0.5">{suggestion.detail}</p>
          <p className="text-xs text-blue-600 mt-1 font-medium">{suggestion.action}</p>
        </div>
      </div>
    </div>
  );
}

export default function ValidationPanel({ report, onColorByConfidence, onFocusResidues }: ValidationPanelProps) {
  const [expandedSection, setExpandedSection] = useState<string | null>('summary');

  const toggleSection = (section: string) => {
    setExpandedSection(expandedSection === section ? null : section);
  };

  // Downsample pLDDT data for chart (max 200 bars)
  const plddtChartData = React.useMemo(() => {
    const data = report.plddt_per_residue;
    if (data.length <= 200) return data;
    const step = Math.ceil(data.length / 200);
    return data.filter((_, i) => i % step === 0);
  }, [report.plddt_per_residue]);

  return (
    <div className="space-y-3 text-sm">
      {/* Grade Header */}
      <div className="flex items-center justify-between p-3 rounded-lg bg-gradient-to-r from-indigo-50 to-purple-50 border border-indigo-100">
        <div className="flex items-center gap-3">
          <Shield className="w-5 h-5 text-indigo-500" />
          <div>
            <p className="font-semibold text-gray-900">Structure Validation</p>
            <p className="text-xs text-gray-500">
              {report.total_residues} residues across {report.chains.length} chain{report.chains.length !== 1 ? 's' : ''}
            </p>
          </div>
        </div>
        <div className={`px-4 py-2 rounded-lg border-2 font-bold text-2xl ${GRADE_COLORS[report.grade] || GRADE_COLORS['N/A']}`}>
          {report.grade}
        </div>
      </div>

      {/* Score Bar */}
      <div className="px-3">
        <div className="flex justify-between text-xs text-gray-500 mb-1">
          <span>Overall Score</span>
          <span>{report.overall_score}/100</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className="h-2 rounded-full transition-all"
            style={{
              width: `${Math.min(100, report.overall_score)}%`,
              backgroundColor: report.overall_score >= 70 ? '#22c55e' : report.overall_score >= 50 ? '#eab308' : '#ef4444',
            }}
          />
        </div>
      </div>

      {/* Suggestions */}
      {report.suggestions.length > 0 && (
        <div className="space-y-2 px-1">
          {report.suggestions.map((s, i) => (
            <SuggestionCard key={i} suggestion={s} />
          ))}
        </div>
      )}

      {/* pLDDT Section */}
      <div className="border rounded-lg overflow-hidden">
        <button
          onClick={() => toggleSection('plddt')}
          className="w-full flex items-center justify-between p-3 bg-gray-50 hover:bg-gray-100 transition-colors"
        >
          <span className="font-medium text-gray-700">pLDDT Confidence</span>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">Mean: {report.plddt_mean.toFixed(1)}</span>
            {expandedSection === 'plddt' ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </div>
        </button>
        {expandedSection === 'plddt' && (
          <div className="p-3 space-y-3">
            {/* Legend */}
            <div className="flex gap-3 text-xs">
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded" style={{ backgroundColor: PLDDT_COLORS.veryHigh }} /> Very High (90+)</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded" style={{ backgroundColor: PLDDT_COLORS.high }} /> High (70-90)</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded" style={{ backgroundColor: PLDDT_COLORS.low }} /> Low (50-70)</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded" style={{ backgroundColor: PLDDT_COLORS.veryLow }} /> Very Low (&lt;50)</span>
            </div>
            {/* Bar Chart */}
            {plddtChartData.length > 0 && (
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={plddtChartData} margin={{ top: 5, right: 5, bottom: 5, left: -10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="residue_number" tick={{ fontSize: 10 }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
                  <Tooltip
                    formatter={(value: number) => [value.toFixed(1), 'pLDDT']}
                    labelFormatter={(label) => `Residue ${label}`}
                  />
                  <Bar dataKey="plddt" radius={[1, 1, 0, 0]}>
                    {plddtChartData.map((entry, i) => (
                      <Cell key={i} fill={plddtColor(entry.plddt)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
            {/* Stats */}
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="p-2 bg-blue-50 rounded">
                <span className="text-blue-700 font-medium">{report.plddt_high_confidence}</span> high confidence (70+)
              </div>
              <div className="p-2 bg-orange-50 rounded">
                <span className="text-orange-700 font-medium">{report.plddt_low_confidence}</span> low confidence (&lt;50)
              </div>
            </div>
            {onColorByConfidence && (
              <button
                onClick={onColorByConfidence}
                className="w-full py-1.5 text-xs bg-indigo-50 text-indigo-600 rounded hover:bg-indigo-100 transition-colors font-medium"
              >
                Color structure by confidence in 3D viewer
              </button>
            )}
          </div>
        )}
      </div>

      {/* Ramachandran Section */}
      <div className="border rounded-lg overflow-hidden">
        <button
          onClick={() => toggleSection('rama')}
          className="w-full flex items-center justify-between p-3 bg-gray-50 hover:bg-gray-100 transition-colors"
        >
          <span className="font-medium text-gray-700">Ramachandran Analysis</span>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">{report.rama_favored_pct.toFixed(1)}% favored</span>
            {expandedSection === 'rama' ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </div>
        </button>
        {expandedSection === 'rama' && (
          <div className="p-3 space-y-3">
            {/* Scatter Plot */}
            {report.rama_data.length > 0 && (
              <ResponsiveContainer width="100%" height={250}>
                <ScatterChart margin={{ top: 10, right: 10, bottom: 20, left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis
                    dataKey="phi" name="Phi" type="number"
                    domain={[-180, 180]} tick={{ fontSize: 10 }}
                    label={{ value: 'Phi (deg)', position: 'bottom', fontSize: 10 }}
                  />
                  <YAxis
                    dataKey="psi" name="Psi" type="number"
                    domain={[-180, 180]} tick={{ fontSize: 10 }}
                    label={{ value: 'Psi (deg)', angle: -90, position: 'insideLeft', fontSize: 10 }}
                  />
                  <Tooltip
                    formatter={(value: number) => value.toFixed(1)}
                    labelFormatter={() => ''}
                    content={({ payload }) => {
                      if (!payload || !payload.length) return null;
                      const d = payload[0]?.payload;
                      if (!d) return null;
                      return (
                        <div className="bg-white p-2 border rounded shadow text-xs">
                          <p className="font-medium">{d.chain_id}:{d.residue_number} {d.residue_name}</p>
                          <p>Phi: {d.phi.toFixed(1)} Psi: {d.psi.toFixed(1)}</p>
                          <p className={d.region === 'outlier' ? 'text-red-600' : 'text-green-600'}>{d.region}</p>
                        </div>
                      );
                    }}
                  />
                  <ReferenceLine x={0} stroke="#ccc" />
                  <ReferenceLine y={0} stroke="#ccc" />
                  <Scatter data={report.rama_data}>
                    {report.rama_data.map((entry, i) => (
                      <Cell key={i} fill={ramaColor(entry.region)} fillOpacity={0.7} r={3} />
                    ))}
                  </Scatter>
                </ScatterChart>
              </ResponsiveContainer>
            )}
            {/* Stats */}
            <div className="grid grid-cols-3 gap-2 text-xs">
              <div className="p-2 bg-green-50 rounded text-center">
                <p className="text-green-700 font-bold">{report.rama_favored}</p>
                <p className="text-green-600">Favored</p>
              </div>
              <div className="p-2 bg-yellow-50 rounded text-center">
                <p className="text-yellow-700 font-bold">{report.rama_allowed}</p>
                <p className="text-yellow-600">Allowed</p>
              </div>
              <div className="p-2 bg-red-50 rounded text-center">
                <p className="text-red-700 font-bold">{report.rama_outlier}</p>
                <p className="text-red-600">Outliers</p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Clashes Section */}
      <div className="border rounded-lg overflow-hidden">
        <button
          onClick={() => toggleSection('clashes')}
          className="w-full flex items-center justify-between p-3 bg-gray-50 hover:bg-gray-100 transition-colors"
        >
          <span className="font-medium text-gray-700">Steric Clashes</span>
          <div className="flex items-center gap-2">
            <span className={`text-xs ${report.clash_count > 0 ? 'text-orange-600' : 'text-green-600'}`}>
              {report.clash_count} clash{report.clash_count !== 1 ? 'es' : ''}
            </span>
            {expandedSection === 'clashes' ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </div>
        </button>
        {expandedSection === 'clashes' && (
          <div className="p-3">
            {report.clash_count === 0 ? (
              <p className="text-xs text-green-600 flex items-center gap-1">
                <CheckCircle className="w-3 h-3" /> No steric clashes detected
              </p>
            ) : (
              <div className="space-y-1 max-h-32 overflow-y-auto">
                {report.clash_details.slice(0, 20).map((clash, i) => (
                  <div key={i} className="flex justify-between text-xs py-1 border-b border-gray-100 last:border-0">
                    <span className="text-gray-600">{clash.atom1} - {clash.atom2}</span>
                    <span className="text-orange-600 font-mono">{clash.distance} A</span>
                  </div>
                ))}
                {report.clash_details.length > 20 && (
                  <p className="text-xs text-gray-400 pt-1">...and {report.clash_details.length - 20} more</p>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
cd "/Users/alizabista/.claude-worktrees/novoprotien-ai-main 2/strange-keller"
git add src/components/ValidationPanel.tsx src/types/validation.ts
git commit -m "feat: add ValidationPanel component with pLDDT chart, Ramachandran plot, and suggestions"
```

---

## Task 7: Frontend - Integrate Validation into ChatPanel

When the validation agent returns a result, render the `ValidationPanel` inside the chat message. Follow the same pattern as `renderAlphaFoldResult`.

**Files:**
- Modify: `src/components/ChatPanel.tsx`

**Step 1: Add validationResult to ExtendedMessage interface**

Find the `ExtendedMessage` interface in `ChatPanel.tsx` and add:
```typescript
  validationResult?: import('../types/validation').ValidationReport;
```

**Step 2: Add renderValidationResult method**

Add a new render method following the pattern of `renderAlphaFoldResult`:

```typescript
import ValidationPanel from './ValidationPanel';
import type { ValidationReport } from '../types/validation';

// Inside the ChatPanel component, add this render method:
const renderValidationResult = (report: ValidationReport) => (
  <div className="mt-3 rounded-lg overflow-hidden border border-indigo-200 bg-gradient-to-br from-indigo-50 to-purple-50 p-4">
    <ValidationPanel
      report={report}
      onColorByConfidence={() => {
        // Generate MolStar code to color by B-factor (pLDDT)
        const code = `
async function colorByConfidence() {
  // Color the current structure by B-factor (pLDDT confidence)
  const data = plugin.managers.structure.hierarchy.current.structures;
  if (data.length > 0) {
    const struct = data[0];
    await plugin.builders.structure.representation.addRepresentation(struct.cell.obj?.data, {
      type: 'cartoon',
      color: 'uncertainty',
    });
  }
}
colorByConfidence();`;
        setCurrentCode(code);
        setPendingCodeToRun(code);
      }}
    />
  </div>
);
```

**Step 3: Add detection of validation results in message processing**

In the message handling logic where agent responses are parsed (look for where `alphafoldResult` is detected from JSON), add similar detection:

```typescript
// When parsing agent response text that contains JSON:
try {
  const parsed = JSON.parse(messageText);
  if (parsed.action === 'validation_result') {
    // Add as validationResult on the message
    newMessage.validationResult = parsed as ValidationReport;
    newMessage.content = `Structure validation complete - Grade: ${parsed.grade}`;
  }
} catch {}
```

**Step 4: Add rendering in the message display**

In the JSX where messages are rendered (near `renderAlphaFoldResult`), add:

```typescript
{message.validationResult && renderValidationResult(message.validationResult)}
```

**Step 5: Commit**

```bash
cd "/Users/alizabista/.claude-worktrees/novoprotien-ai-main 2/strange-keller"
git add src/components/ChatPanel.tsx
git commit -m "feat: integrate ValidationPanel into ChatPanel message rendering"
```

---

## Task 8: Frontend - Add "Validate" Button to Result Cards

Add a "Validate" button on AlphaFold and OpenFold2 result cards so users can one-click validate a predicted structure.

**Files:**
- Modify: `src/components/ChatPanel.tsx`

**Step 1: Add validate handler function**

Inside the ChatPanel component, add a handler:

```typescript
const handleValidateStructure = async (pdbContent: string) => {
  try {
    const { validateStructure } = await import('../utils/api');

    // Add a "validating..." message
    addMessage({
      role: 'assistant',
      content: 'Running structure validation...',
    });

    const report = await validateStructure(pdbContent);

    // Replace with validation result
    addMessage({
      role: 'assistant',
      content: `Structure validation complete - Grade: ${report.grade}`,
      validationResult: report,
    });
  } catch (error) {
    addMessage({
      role: 'assistant',
      content: `Validation failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
    });
  }
};
```

**Step 2: Add Validate button to AlphaFold result card**

In `renderAlphaFoldResult`, add a button after the existing "View 3D" button:

```typescript
<button
  onClick={() => handleValidateStructure(result.pdbContent!)}
  className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-50 text-indigo-600 rounded-lg text-xs font-medium hover:bg-indigo-100 transition-colors"
  disabled={!result.pdbContent}
>
  <Shield className="w-3.5 h-3.5" />
  Validate
</button>
```

**Step 3: Add Validate button to OpenFold2 result card**

Same pattern in `renderOpenFold2Result`.

**Step 4: Commit**

```bash
cd "/Users/alizabista/.claude-worktrees/novoprotien-ai-main 2/strange-keller"
git add src/components/ChatPanel.tsx
git commit -m "feat: add Validate button to AlphaFold and OpenFold2 result cards"
```

---

## Task 9: Pipeline Canvas - Validation Node

Add a `validation_node` to the pipeline canvas so it can be used in automated design-validate workflows.

**Files:**
- Create: `src/components/pipeline-canvas/nodes/validation_node/node.json`
- Modify: `src/components/pipeline-canvas/types/index.ts` (add type)
- Modify: `src/components/pipeline-canvas/utils/nodeLoader.ts` (register node)

**Step 1: Create the node JSON config**

Create `src/components/pipeline-canvas/nodes/validation_node/node.json`:

```json
{
  "metadata": {
    "type": "validation_node",
    "label": "Validation",
    "icon": "Shield",
    "color": "#6366f1",
    "borderColor": "border-indigo-500",
    "bgColor": "bg-indigo-500",
    "description": "Structure quality validation"
  },
  "schema": {
    "min_score": {
      "type": "number",
      "required": false,
      "default": 70,
      "min": 0,
      "max": 100,
      "label": "Minimum Score",
      "helpText": "Minimum overall quality score to pass validation (0-100)"
    },
    "max_outliers_pct": {
      "type": "number",
      "required": false,
      "default": 5,
      "min": 0,
      "max": 100,
      "label": "Max Ramachandran Outliers %",
      "helpText": "Maximum percentage of Ramachandran outliers allowed"
    }
  },
  "handles": {
    "inputs": [
      {
        "id": "target",
        "type": "target",
        "position": "left",
        "dataType": "pdb_file"
      }
    ],
    "outputs": [
      {
        "id": "source",
        "type": "source",
        "position": "right",
        "dataType": "validation_report"
      }
    ]
  },
  "execution": {
    "type": "api_call",
    "endpoint": "/validation/validate",
    "method": "POST",
    "payload": {
      "pdb_content": "{{input.target}}",
      "min_score": "{{config.min_score}}",
      "max_outliers_pct": "{{config.max_outliers_pct}}"
    }
  },
  "defaultConfig": {
    "min_score": 70,
    "max_outliers_pct": 5
  }
}
```

**Step 2: Add `validation_node` to the NodeType union**

In `src/components/pipeline-canvas/types/index.ts`, update:

```typescript
export type NodeType = 'input_node' | 'rfdiffusion_node' | 'proteinmpnn_node' | 'alphafold_node' | 'openfold2_node' | 'message_input_node' | 'http_request_node' | 'validation_node';
```

And add to `NodeConfig`:
```typescript
  // Validation Node
  min_score?: number;
  max_outliers_pct?: number;
```

**Step 3: Register the node in nodeLoader.ts**

Check how existing nodes are loaded in `nodeLoader.ts` and add `validation_node` to the same list/import pattern. The exact change depends on how the loader works - it may auto-discover from the `nodes/` directory or have an explicit list.

**Step 4: Commit**

```bash
cd "/Users/alizabista/.claude-worktrees/novoprotien-ai-main 2/strange-keller"
git add src/components/pipeline-canvas/nodes/validation_node/ src/components/pipeline-canvas/types/index.ts src/components/pipeline-canvas/utils/nodeLoader.ts
git commit -m "feat: add validation_node to pipeline canvas"
```

---

## Task 10: MolStar Confidence Coloring

Add a `colorByConfidence` method to `molstarBuilder.ts` so the 3D viewer can color structures by pLDDT score using the B-factor column.

**Files:**
- Modify: `src/utils/molstarBuilder.ts`

**Step 1: Add colorByConfidence to the MolstarBuilder interface**

Add to the `MolstarBuilder` interface:
```typescript
  colorByConfidence: () => Promise<void>;
```

**Step 2: Implement the method**

Add inside the `createMolstarBuilder` return object:

```typescript
    async colorByConfidence() {
      if (!currentStructure) {
        throw new Error('No structure loaded');
      }

      try {
        // Clear existing representations
        const hierarchy = plugin.managers.structure.hierarchy;
        const existing = (hierarchy as any)?.current?.structures ?? [];
        if (Array.isArray(existing) && existing.length > 0) {
          for (const s of existing) {
            const components = s?.components ?? [];
            for (const comp of components) {
              const representations = comp?.representations ?? [];
              for (const repr of representations) {
                await plugin.managers.structure.hierarchy.remove([repr]);
              }
            }
          }
        }

        // Add cartoon with uncertainty (B-factor / pLDDT) coloring
        await plugin.builders.structure.representation.addRepresentation(
          currentStructure,
          {
            type: 'cartoon' as const,
            color: 'uncertainty' as const,
          }
        );

        console.log('[Molstar] Colored by confidence (B-factor/pLDDT)');
      } catch (error) {
        console.warn('Failed to color by confidence:', error);
        // Fallback: just re-apply cartoon with element coloring
        await plugin.builders.structure.representation.addRepresentation(
          currentStructure,
          {
            type: 'cartoon' as const,
            color: 'element' as const,
          }
        );
      }
    },
```

**Step 3: Commit**

```bash
cd "/Users/alizabista/.claude-worktrees/novoprotien-ai-main 2/strange-keller"
git add src/utils/molstarBuilder.ts
git commit -m "feat: add colorByConfidence method to MolstarBuilder for pLDDT visualization"
```

---

## Task 11: Backend - Pass PDB Content Through Agent Context

Ensure the validation handler can access the current viewer's PDB content when triggered via chat. This requires threading the PDB content through the agent invocation.

**Files:**
- Modify: `server/app.py` (accept `pdb_content` in route request)
- Modify: `server/agents/runner.py` (pass it through to handler)

**Step 1: Update the `/api/agents/route` endpoint**

In `server/app.py`, find the `/api/agents/route` endpoint. It receives a body with `input`, `selection`, etc. Add `pdb_content` to the fields extracted from the body:

```python
pdb_content = body.get("pdb_content")
```

And pass it through to `run_agent`:
```python
result = await run_agent(agent, user_text, ..., pdb_content=pdb_content)
```

**Step 2: Update run_agent signature**

In `server/agents/runner.py`, add `pdb_content: Optional[str] = None` parameter to `run_agent()` and alias it as `current_pdb_content` for the validation handler context.

**Step 3: Update frontend to send PDB content with chat**

In the frontend chat submission (in `ChatPanel.tsx`), when sending a message to the agent route, include the current PDB content if available. Look for where the POST to `/api/agents/route` is made and add:

```typescript
pdb_content: currentPdbContent, // from app store or state
```

This requires getting the current PDB content from the viewer. If it's not already stored in state, you may need to store it when a structure is loaded (e.g., in `useAppStore`).

**Step 4: Commit**

```bash
cd "/Users/alizabista/.claude-worktrees/novoprotien-ai-main 2/strange-keller"
git add server/app.py server/agents/runner.py src/components/ChatPanel.tsx
git commit -m "feat: thread PDB content through agent context for validation"
```

---

## Task 12: Integration Test - End-to-End Validation Flow

Test the full flow manually and write a basic integration test.

**Files:**
- Create: `tests/test_validation.py`

**Step 1: Write a backend test for the validator**

Create `tests/test_validation.py`:

```python
"""Test the structure validation engine."""

import sys
import os

# Add server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

from tools.validation.structure_validator import validate_structure, ValidationReport


# A minimal valid PDB with B-factors (simulated pLDDT)
SAMPLE_PDB = """ATOM      1  N   ALA A   1       1.000   1.000   1.000  1.00 85.00           N
ATOM      2  CA  ALA A   1       2.000   1.000   1.000  1.00 85.00           C
ATOM      3  C   ALA A   1       3.000   1.000   1.000  1.00 85.00           C
ATOM      4  O   ALA A   1       3.000   2.000   1.000  1.00 85.00           O
ATOM      5  N   GLY A   2       4.000   1.000   1.000  1.00 72.00           N
ATOM      6  CA  GLY A   2       5.000   1.000   1.000  1.00 72.00           C
ATOM      7  C   GLY A   2       6.000   1.000   1.000  1.00 72.00           C
ATOM      8  O   GLY A   2       6.000   2.000   1.000  1.00 72.00           O
ATOM      9  N   VAL A   3       7.000   1.000   1.000  1.00 45.00           N
ATOM     10  CA  VAL A   3       8.000   1.000   1.000  1.00 45.00           C
ATOM     11  C   VAL A   3       9.000   1.000   1.000  1.00 45.00           C
ATOM     12  O   VAL A   3       9.000   2.000   1.000  1.00 45.00           O
END
"""


def test_validate_structure_returns_report():
    """validate_structure returns a ValidationReport with grade and metrics."""
    report = validate_structure(SAMPLE_PDB)
    assert isinstance(report, ValidationReport)
    assert report.grade in ("A", "B", "C", "D", "F", "N/A", "ERR")
    assert report.total_residues >= 0
    assert report.overall_score >= 0
    print(f"Grade: {report.grade}, Score: {report.overall_score}, Residues: {report.total_residues}")


def test_plddt_values_extracted():
    """pLDDT values are correctly extracted from B-factor column."""
    report = validate_structure(SAMPLE_PDB)
    if report.plddt_per_residue:
        values = [r["plddt"] for r in report.plddt_per_residue]
        assert all(0 <= v <= 100 for v in values if v is not None)
        print(f"pLDDT values: {values}")


def test_empty_pdb_returns_error():
    """Empty PDB content returns an error suggestion."""
    report = validate_structure("")
    assert report.suggestions
    print(f"Empty PDB result: {report.suggestions[0]}")


def test_suggestions_generated():
    """Suggestions are generated based on metrics."""
    report = validate_structure(SAMPLE_PDB)
    assert isinstance(report.suggestions, list)
    for s in report.suggestions:
        assert "type" in s
        assert "message" in s
        assert "action" in s
    print(f"Suggestions: {[s['type'] for s in report.suggestions]}")


if __name__ == "__main__":
    test_validate_structure_returns_report()
    test_plddt_values_extracted()
    test_empty_pdb_returns_error()
    test_suggestions_generated()
    print("\nAll tests passed!")
```

**Step 2: Run the tests**

```bash
cd "/Users/alizabista/.claude-worktrees/novoprotien-ai-main 2/strange-keller"
source server/venv/bin/activate
python tests/test_validation.py
```

Expected: `All tests passed!`

**Step 3: Commit**

```bash
cd "/Users/alizabista/.claude-worktrees/novoprotien-ai-main 2/strange-keller"
git add tests/test_validation.py
git commit -m "test: add validation engine integration tests"
```

---

## Task 13: Verify Full Stack

**Step 1: Start the development server**

```bash
cd "/Users/alizabista/.claude-worktrees/novoprotien-ai-main 2/strange-keller"
npm run dev:all
```

**Step 2: Manual smoke test checklist**

1. Open browser at `http://localhost:3000`
2. Load a structure (e.g., type "show PDB:1CRN")
3. Type "validate this structure" in chat
4. Verify: Validation agent is routed (check server logs for `rule:validation-keywords`)
5. Verify: ValidationPanel renders with grade, charts, suggestions
6. Click "Color structure by confidence" button
7. Verify: MolStar updates to show uncertainty/pLDDT coloring
8. Run AlphaFold2 on a short sequence
9. On the result card, click "Validate" button
10. Verify: New validation message appears with quality report

**Step 3: Check pipeline canvas**

1. Switch to Pipeline view
2. Add a validation_node from palette
3. Connect AlphaFold output → Validation input
4. Verify: Node renders with indigo color and Shield icon

**Step 4: Final commit (if any fixes needed)**

```bash
cd "/Users/alizabista/.claude-worktrees/novoprotien-ai-main 2/strange-keller"
git add -A
git commit -m "fix: address integration issues from smoke testing"
```

---

## Summary of All Files

### Created (new files):
| File | Purpose |
|------|---------|
| `server/tools/validation/__init__.py` | Package init |
| `server/tools/validation/structure_validator.py` | Core validation engine (pLDDT, Ramachandran, clashes) |
| `server/agents/handlers/validation.py` | Validation request handler |
| `server/agents/prompts/validation.py` | Agent system prompt |
| `src/types/validation.ts` | TypeScript types for validation data |
| `src/components/ValidationPanel.tsx` | Full validation UI with charts |
| `src/components/pipeline-canvas/nodes/validation_node/node.json` | Pipeline node config |
| `tests/test_validation.py` | Integration tests |

### Modified (existing files):
| File | Change |
|------|--------|
| `package.json` | Add recharts dependency |
| `server/requirements.txt` | Add biopython, numpy |
| `server/agents/registry.py` | Register validation-agent |
| `server/agents/runner.py` | Add handler dispatch for validation |
| `server/agents/router.py` | Add keyword routing rules |
| `server/app.py` | Add `/api/validation/validate` endpoint |
| `src/utils/api.ts` | Add `validateStructure()` function |
| `src/utils/molstarBuilder.ts` | Add `colorByConfidence()` method |
| `src/components/ChatPanel.tsx` | Render validation results, add Validate buttons |
| `src/components/pipeline-canvas/types/index.ts` | Add `validation_node` type |
| `src/components/pipeline-canvas/utils/nodeLoader.ts` | Register validation node |
