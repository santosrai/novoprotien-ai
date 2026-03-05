"""AF2Bind binding-site prediction handler.

Calls an external AF2Bind API server (e.g. Colab GPU notebook) and returns
per-residue binding probabilities + an output PDB with B-factors = scores.
"""

from __future__ import annotations

import asyncio
import csv
import io
import os
import re
from typing import Any, Dict, Optional

import httpx

try:
    from ...infrastructure.utils import log_line
except ImportError:
    try:
        from infrastructure.utils import log_line
    except ImportError:
        def log_line(tag: str, data: Any = None) -> None:
            print(f"[{tag}] {data}")


class AF2BindHandler:
    """Thin client that talks to the external AF2Bind FastAPI server."""

    PDB_RE = re.compile(r"\b(\d[A-Za-z0-9]{3})\b")
    UNIPROT_RE = re.compile(r"\b([A-Z][0-9][A-Z0-9]{3}[0-9])\b")
    CHAIN_RE = re.compile(r"\bchain\s+([A-Z])\b", re.IGNORECASE)

    @property
    def api_url(self) -> str:
        return os.getenv("AF2BIND_API_URL", "http://localhost:8000").rstrip("/")

    @property
    def api_key(self) -> str:
        return os.getenv("AF2BIND_API_KEY", "")

    # ── public entry point ──────────────────────────────────────────

    async def process_request(
        self,
        input_text: str,
        context: Optional[Dict] = None,
        abort_event: Optional[asyncio.Event] = None,
    ) -> Dict[str, Any]:
        target_id, id_type = self._parse_target(input_text)
        if not target_id:
            return {
                "action": "error",
                "error": (
                    "Could not find a PDB ID (e.g. 1ZNI) or UniProt ID "
                    "(e.g. Q6DG85) in your message. Please specify a target."
                ),
            }

        chain = self._parse_chain(input_text)
        log_line("af2bind:request", {
            "target": target_id,
            "type": id_type,
            "chain": chain,
        })

        try:
            result = await self._call_api(target_id, chain, abort_event=abort_event)
        except httpx.ConnectError:
            return {
                "action": "error",
                "error": (
                    f"Cannot connect to AF2Bind API at {self.api_url}. "
                    "Make sure the AF2Bind server is running and "
                    "AF2BIND_API_URL is set correctly in your .env file."
                ),
            }
        except httpx.TimeoutException:
            return {
                "action": "error",
                "error": (
                    "AF2Bind request timed out (>10 min). The prediction may "
                    "be taking too long for this protein. Try a shorter chain."
                ),
            }
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            detail = exc.response.text[:200]
            return {
                "action": "error",
                "error": f"AF2Bind API returned HTTP {status}: {detail}",
            }
        except Exception as exc:
            log_line("af2bind:error", {"error": str(exc)})
            return {
                "action": "error",
                "error": f"AF2Bind prediction failed: {exc}",
            }

        # Parse the CSV into structured residue data
        residues = self._parse_csv(result.get("results_csv", ""))
        top_residues = sorted(residues, key=lambda r: r["pBind"], reverse=True)[:15]
        high_conf_count = sum(1 for r in residues if r["pBind"] > 0.5)
        compute_time = result.get("seconds", 0)

        summary = (
            f"**AF2Bind** predicted binding sites for **{target_id}** "
            f"(chain {chain}).\n\n"
            f"Analyzed **{len(residues)}** residues in **{compute_time:.1f}s**. "
            f"Found **{high_conf_count}** residues with p(bind) > 0.5.\n\n"
        )
        if top_residues:
            summary += "**Top predicted binding residues:**\n"
            for i, r in enumerate(top_residues[:5], 1):
                summary += (
                    f"{i}. {r['resn']}{r['resi']} (chain {r['chain']}) — "
                    f"p(bind) = {r['pBind']:.3f}\n"
                )

        return {
            "text": summary,
            "af2bindResult": {
                "targetId": target_id,
                "chain": chain,
                "pdbContent": result.get("output_pdb", ""),
                "residues": residues,
                "topResidues": top_residues,
                "computeTime": compute_time,
                "totalResidues": len(residues),
            },
        }

    # ── private helpers ─────────────────────────────────────────────

    def _parse_target(self, text: str) -> tuple[str, str]:
        """Extract PDB ID or UniProt ID from user text."""
        # Try UniProt first (more specific pattern)
        m = self.UNIPROT_RE.search(text)
        if m:
            return m.group(1).upper(), "uniprot"
        # Then PDB
        m = self.PDB_RE.search(text)
        if m:
            return m.group(1).upper(), "pdb"
        return "", ""

    def _parse_chain(self, text: str) -> str:
        """Extract chain letter from text, default 'A'."""
        m = self.CHAIN_RE.search(text)
        return m.group(1).upper() if m else "A"

    async def _call_api(
        self,
        target_pdb: str,
        chain: str,
        abort_event: Optional[asyncio.Event] = None,
    ) -> Dict[str, Any]:
        """POST to the external AF2Bind API server.

        If *abort_event* is provided, the HTTP request is raced against it so
        the user can cancel the potentially 10-minute GPU call.
        """
        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        async with httpx.AsyncClient(timeout=600.0) as client:
            request_coro = client.post(
                f"{self.api_url}/af2bind",
                json={
                    "target_pdb": target_pdb,
                    "target_chain": chain,
                    "mask_sidechains": True,
                    "mask_sequence": False,
                },
                headers=headers,
            )

            if abort_event is not None:
                # Race the HTTP request against the abort signal
                request_task = asyncio.create_task(request_coro)
                abort_task = asyncio.create_task(abort_event.wait())
                done, pending = await asyncio.wait(
                    {request_task, abort_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for t in pending:
                    t.cancel()
                if abort_task in done:
                    raise asyncio.CancelledError("Aborted by user")
                resp = request_task.result()
            else:
                resp = await request_coro

            resp.raise_for_status()
            return resp.json()

    def _parse_csv(self, csv_text: str) -> list[Dict[str, Any]]:
        """Parse AF2Bind results CSV into list of residue dicts."""
        if not csv_text or not csv_text.strip():
            return []
        reader = csv.DictReader(io.StringIO(csv_text))
        residues = []
        for row in reader:
            try:
                residues.append({
                    "chain": row.get("chain", "A"),
                    "resi": int(row.get("resi", 0)),
                    "resn": row.get("resn", "X"),
                    "pBind": float(row.get("p(bind)", 0.0)),
                })
            except (ValueError, TypeError):
                continue
        return residues


# Module-level singleton
af2bind_handler = AF2BindHandler()
