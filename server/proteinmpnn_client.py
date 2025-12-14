"""Async client for interacting with NVIDIA ProteinMPNN API."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import ssl
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import aiohttp

try:
    import certifi
except ImportError:  # pragma: no cover - optional dependency
    certifi = None


def setup_proteinmpnn_logging() -> logging.Logger:
    """Configure dedicated logfile for ProteinMPNN API calls."""
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)

    logger = logging.getLogger("proteinmpnn.api")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.FileHandler(log_dir / "proteinmpnn_api.log", encoding="utf-8")
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


api_logger = setup_proteinmpnn_logging()
logger = logging.getLogger(__name__)


class ProteinMPNNClient:
    """Client wrapper around the NVIDIA IPD ProteinMPNN deployment."""

    def __init__(self) -> None:
        api_key = os.getenv("PROTEINMPNN_API_KEY") or os.getenv("NVCF_RUN_KEY")
        if not api_key:
            raise ValueError(
                "ProteinMPNN API key not configured. Set PROTEINMPNN_API_KEY or NVCF_RUN_KEY."
            )

        self.api_key = api_key
        # Base inference endpoint; override via env for custom deployments
        self.base_url = (
            os.getenv("PROTEINMPNN_URL")
            or "https://health.api.nvidia.com/v1/biology/ipd/proteinmpnn/predict"
        )
        # Optional separate status URL (falls back to base_url/{job_id})
        self.status_url = os.getenv("PROTEINMPNN_STATUS_URL")

        self.poll_interval = max(5, int(os.getenv("PROTEINMPNN_POLL_INTERVAL", "10")))
        self.max_polls = int(os.getenv("PROTEINMPNN_MAX_POLLS", "0"))
        self.max_wait_seconds = int(os.getenv("PROTEINMPNN_MAX_WAIT_SECONDS", "1800"))
        self.request_timeout = int(os.getenv("PROTEINMPNN_REQUEST_TIMEOUT", "240"))
        self.poll_timeout = int(os.getenv("PROTEINMPNN_POLL_TIMEOUT", "60"))
        self.post_retries = int(os.getenv("PROTEINMPNN_POST_RETRIES", "3"))

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def create_payload(
        self,
        pdb_content: str,
        *,
        num_designs: int = 1,
        temperature: float = 0.1,
        chain_ids: Optional[list[str]] = None,
        fixed_positions: Optional[list[str]] = None,
        random_seed: Optional[int] = None,
        extra_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "input_pdb": pdb_content,
            "ca_only": False,
            "use_soluble_model": False,
            "sampling_temp": [max(0.0, temperature)],
        }
        # Note: num_designs is handled by repeating the sampling_temp values
        if num_designs > 1:
            payload["sampling_temp"] = [max(0.0, temperature)] * min(num_designs, 20)
        
        if chain_ids:
            payload["chain_ids"] = chain_ids
        if fixed_positions:
            payload["fixed_positions"] = fixed_positions
        if random_seed is not None:
            payload["random_seed"] = random_seed
        if extra_options:
            payload.update(extra_options)
        return payload

    async def submit_design_job(
        self,
        pdb_content: str,
        *,
        num_designs: int = 1,
        temperature: float = 0.1,
        chain_ids: Optional[list[str]] = None,
        fixed_positions: Optional[list[str]] = None,
        random_seed: Optional[int] = None,
        extra_options: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Submit a design job and poll until completion."""

        payload = self.create_payload(
            pdb_content,
            num_designs=num_designs,
            temperature=temperature,
            chain_ids=chain_ids,
            fixed_positions=fixed_positions,
            random_seed=random_seed,
            extra_options=extra_options,
        )

        api_logger.info(
            "Submitting ProteinMPNN job | sampling_temp=%s chains=%s",
            payload.get("sampling_temp"),
            chain_ids,
        )
        api_logger.debug("Payload preview: %s", json.dumps({k: v for k, v in payload.items() if k != "input_pdb"})[:500])

        ssl_context = ssl.create_default_context()
        if certifi is not None:
            try:
                ssl_context.load_verify_locations(certifi.where())
            except Exception as exc:  # pragma: no cover - defensive logging
                api_logger.warning("Failed to load certifi bundle: %s", exc)
        timeout = aiohttp.ClientTimeout(total=self.request_timeout)

        attempt = 0
        last_error: Optional[str] = None
        async with aiohttp.ClientSession(timeout=timeout) as session:
            while attempt < max(1, self.post_retries):
                attempt += 1
                try:
                    async with session.post(
                        self.base_url,
                        headers=self.headers,
                        json=payload,
                        ssl=ssl_context,
                    ) as response:
                        api_logger.info(
                            "ProteinMPNN POST attempt %s returned HTTP %s",
                            attempt,
                            response.status,
                        )
                        if response.status in (200, 201, 202):
                            data = await response.json()
                            api_logger.info("ProteinMPNN API response: %s", json.dumps(data, indent=2)[:1000])
                            api_logger.info("ProteinMPNN response headers: %s", dict(response.headers))
                            
                            # ProteinMPNN is synchronous - results are returned immediately
                            if progress_callback:
                                progress_callback("ProteinMPNN design complete", 100)
                            return {"status": "completed", "data": data}
                        body = await response.text()
                        last_error = f"HTTP {response.status}: {body}"[:2000]
                        if response.status >= 500:
                            await asyncio.sleep(min(3 * attempt, 10))
                            continue
                        return {"status": "error", "error": last_error}
                except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                    last_error = str(exc)
                    api_logger.warning("ProteinMPNN POST attempt %s failed: %s", attempt, exc)
                    await asyncio.sleep(min(3 * attempt, 10))
            error_msg = last_error or "ProteinMPNN submission failed"
            return {"status": "error", "error": error_msg}

    def _resolve_run_identifiers(
        self,
        response: aiohttp.ClientResponse,
        data: Dict[str, Any],
    ) -> Tuple[Optional[str], Optional[str]]:
        run_id = (
            data.get("id")
            or data.get("run_id")
            or data.get("job_id")
            or response.headers.get("Nvcf-Job-Id")
        )
        status_url = (
            data.get("status_url")
            or response.headers.get("Location")
            or response.headers.get("Operation-Location")
        )
        if not status_url and run_id:
            status_url = self._build_status_url(run_id)
        return run_id, status_url

    def _build_status_url(self, run_id: str) -> str:
        if self.status_url:
            return f"{self.status_url.rstrip('/')}/{run_id}"
        return f"{self.base_url.rstrip('/')}/runs/{run_id}"

    async def _poll_until_complete(
        self,
        session: aiohttp.ClientSession,
        run_id: str,
        status_url: Optional[str],
        *,
        progress_callback: Optional[Any] = None,
    ) -> Dict[str, Any]:
        poll_url = status_url or self._build_status_url(run_id)
        api_logger.info("Polling ProteinMPNN run %s via %s", run_id, poll_url)

        polls = 0
        elapsed = 0
        start = asyncio.get_event_loop().time()
        consecutive_errors = 0

        while True:
            polls += 1
            if self.max_polls > 0 and polls > self.max_polls:
                return {
                    "status": "timeout",
                    "error": f"Polling exceeded {self.max_polls} attempts",
                }
            if self.max_wait_seconds > 0 and elapsed > self.max_wait_seconds:
                return {
                    "status": "timeout",
                    "error": f"Polling exceeded {self.max_wait_seconds} seconds",
                }

            try:
                timeout = aiohttp.ClientTimeout(total=self.poll_timeout)
                async with session.get(poll_url, headers=self.headers, timeout=timeout) as resp:
                    body = await resp.text()
                    api_logger.debug(
                        "ProteinMPNN poll %s HTTP %s body=%s",
                        polls,
                        resp.status,
                        body[:800],
                    )
                    if resp.status in (200, 201):
                        data = json.loads(body)
                        status = data.get("status", "").lower()
                        if status in {"completed", "succeeded", "success"}:
                            if progress_callback:
                                progress_callback("ProteinMPNN design complete", 100)
                            return {"status": "completed", "data": data}
                        if status in {"failed", "error", "errored"}:
                            return {
                                "status": "error",
                                "error": data.get("error") or body,
                                "data": data,
                            }
                        # still running
                        if progress_callback:
                            progress_callback(
                                f"Design running (status: {status or 'processing'})",
                                min(95, polls * 3),
                            )
                    elif resp.status == 202:
                        if progress_callback:
                            progress_callback("Design queued", min(25, polls * 3))
                    elif resp.status in {500, 502, 503, 504}:
                        api_logger.warning("ProteinMPNN transient poll failure HTTP %s", resp.status)
                        consecutive_errors += 1
                        if consecutive_errors > 5:
                            return {
                                "status": "polling_failed",
                                "error": f"Repeated polling errors, last HTTP {resp.status}",
                            }
                    else:
                        return {
                            "status": "polling_failed",
                            "error": f"Unexpected polling response {resp.status}: {body}",
                        }
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                consecutive_errors += 1
                api_logger.warning("ProteinMPNN polling error attempt %s: %s", polls, exc)
                if consecutive_errors > 5:
                    return {"status": "polling_failed", "error": str(exc)}
            await asyncio.sleep(self.poll_interval)
            elapsed = asyncio.get_event_loop().time() - start


# Convenience factory for dependency injection patterns
_proteinmpnn_client: Optional[ProteinMPNNClient] = None


def get_proteinmpnn_client() -> ProteinMPNNClient:
    global _proteinmpnn_client
    if _proteinmpnn_client is None:
        _proteinmpnn_client = ProteinMPNNClient()
    return _proteinmpnn_client
