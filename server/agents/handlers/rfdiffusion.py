#!/usr/bin/env python3
"""
RFdiffusion request handler for the server.
Integrates request parsing, NIMS API calls, and result processing.
"""

import asyncio
import json
import logging
import os
import sys
import re
from pathlib import Path
from typing import Dict, Any, Optional, List

# Ensure server directory is in Python path for imports
_server_dir = os.path.dirname(os.path.abspath(__file__))
if _server_dir not in sys.path:
    sys.path.insert(0, _server_dir)

# Import dependencies
try:
    # Try relative import first (when imported as module)
    from ...tools.nvidia.rfdiffusion import RFdiffusionClient
    from ...domain.protein.sequence import SequenceExtractor
    from ...domain.storage.pdb_storage import get_uploaded_pdb
    from ...domain.storage.session_tracker import associate_file_with_session
    from ...domain.storage.file_access import save_result_file
except ImportError:
    # Fallback to absolute import (when running directly)
    from tools.nvidia.rfdiffusion import RFdiffusionClient
    from domain.protein.sequence import SequenceExtractor
    from domain.storage.pdb_storage import get_uploaded_pdb
    from domain.storage.session_tracker import associate_file_with_session

logger = logging.getLogger(__name__)

class RFdiffusionHandler:
    """Handles RFdiffusion protein design requests from the frontend"""
    
    def __init__(self):
        self.sequence_extractor = SequenceExtractor()
        self.rfdiffusion_client = None  # Initialize when needed
        self.active_jobs = {}  # Track running jobs
        self.job_results = {}  # Store completed job results
        self.job_owners = {}  # user_id by job_id
    
    def _get_rfdiffusion_client(self) -> RFdiffusionClient:
        """Get or create RFdiffusion client"""
        if not self.rfdiffusion_client:
            try:
                self.rfdiffusion_client = RFdiffusionClient()
            except ValueError as e:
                # RFdiffusion client throws ValueError for missing API key
                logger.error(f"RFdiffusion API configuration error: {e}")
                raise ValueError("RFdiffusion API key not configured. Please set the NVCF_RUN_KEY environment variable with your NVIDIA API key.")
            except Exception as e:
                logger.error(f"Failed to initialize RFdiffusion client: {e}")
                raise ValueError(f"RFdiffusion API initialization failed: {str(e)}")
        return self.rfdiffusion_client
    
    def parse_design_request(self, text: str) -> Dict[str, Any]:
        """
        Parse a natural language request for protein design
        
        Args:
            text: User's design request
            
        Returns:
            Dictionary with parsed information
        """
        text = text.lower()
        result = {
            "type": "design",
            "pdb_id": None,
            "input_pdb": None,
            "contigs": None,
            "hotspot_res": [],
            "diffusion_steps": 15,
            "design_mode": "unconditional"  # unconditional, motif_scaffolding, partial_diffusion
        }
        
        # Look for PDB ID patterns
        pdb_match = re.search(r'pdb[:\s]*([0-9a-z]{4})', text)
        if pdb_match:
            result["pdb_id"] = pdb_match.group(1).upper()
            result["design_mode"] = "motif_scaffolding"
        else:
            # Look for bare 4-character PDB IDs
            bare_pdb_match = re.search(r'\b([0-9][a-z0-9]{3})\b', text)
            if bare_pdb_match:
                result["pdb_id"] = bare_pdb_match.group(1).upper()
                result["design_mode"] = "motif_scaffolding"
        
        # Look for contig patterns
        contig_patterns = [
            r'contigs?\s*[:\s]*["\']?([A-Za-z0-9\-/\s]+)["\']?',
            r'length\s*[:\s]*(\d+)[-\s]*(\d+)',
            r'(\d+)[-\s]*(\d+)\s*residues?',
        ]
        
        for pattern in contig_patterns:
            match = re.search(pattern, text)
            if match:
                if len(match.groups()) == 1:
                    result["contigs"] = match.group(1).strip()
                else:
                    # Convert length specification to contig format
                    start, end = match.groups()
                    result["contigs"] = f"A{start}-{end}"
                break
        
        # Look for hotspot residues
        hotspot_patterns = [
            r'hotspots?\s*[:\s]*\[([A-Z0-9,\s]+)\]',
            r'hotspots?\s*[:\s]*([A-Z]\d+(?:,\s*[A-Z]\d+)*)',
            r'keep\s+residues?\s+([A-Z]\d+(?:,\s*[A-Z]\d+)*)',
        ]
        
        for pattern in hotspot_patterns:
            match = re.search(pattern, text)
            if match:
                hotspots_str = match.group(1)
                # Parse comma-separated residues
                hotspots = [h.strip() for h in hotspots_str.split(',') if h.strip()]
                result["hotspot_res"] = hotspots
                if hotspots:
                    result["design_mode"] = "motif_scaffolding"
                break
        
        # Look for diffusion steps
        steps_match = re.search(r'(\d+)\s*steps?', text)
        if steps_match:
            steps = int(steps_match.group(1))
            if 1 <= steps <= 100:
                result["diffusion_steps"] = steps
        
        # Determine design complexity
        if "complex" in text or "detailed" in text:
            result["complexity"] = "high"
            if result["diffusion_steps"] == 15:  # Default
                result["diffusion_steps"] = 25
        elif "simple" in text or "basic" in text:
            result["complexity"] = "low"
            if result["diffusion_steps"] == 15:  # Default
                result["diffusion_steps"] = 10
        else:
            result["complexity"] = "medium"
        
        return result
    
    async def process_design_request(self, input_text: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Process a natural language design request
        
        Args:
            input_text: User's design request
            context: Optional context (current PDB, selection, etc.)
            
        Returns:
            Dictionary with design parameters for user confirmation
        """
        try:
            # Parse the request
            parsed = self.parse_design_request(input_text)
            logger.info(f"Parsed design request: {parsed}")
            
            # Set default contigs if not specified
            if not parsed["contigs"]:
                if parsed["design_mode"] == "unconditional":
                    parsed["contigs"] = "A50-150"  # Unconditional design
                else:
                    parsed["contigs"] = "A20-60/0 50-100"  # Motif scaffolding
            
            # Validate PDB if specified
            if parsed["pdb_id"]:
                try:
                    # Quick validation that PDB exists
                    sequences = self.sequence_extractor.extract_from_pdb_id(parsed["pdb_id"])
                    if not sequences:
                        return {
                            "error": f"Could not extract sequences from PDB {parsed['pdb_id']}",
                            "action": "error"
                        }
                    pdb_info = f"PDB {parsed['pdb_id']} ({len(sequences)} chains)"
                except Exception as e:
                    return {
                        "error": f"Invalid PDB ID {parsed['pdb_id']}: {str(e)}",
                        "action": "error"
                    }
            else:
                pdb_info = "No template structure"
            
            # Estimate processing time
            estimated_time = self._estimate_time(parsed["diffusion_steps"], parsed.get("complexity", "medium"))
            
            # Create confirmation response
            return {
                "action": "confirm_design",
                "parameters": {
                    "pdb_id": parsed["pdb_id"],
                    "contigs": parsed["contigs"],
                    "hotspot_res": parsed["hotspot_res"],
                    "diffusion_steps": parsed["diffusion_steps"],
                    "design_mode": parsed["design_mode"]
                },
                "design_info": {
                    "mode": parsed["design_mode"],
                    "template": pdb_info,
                    "contigs": parsed["contigs"],
                    "hotspots": len(parsed["hotspot_res"]),
                    "complexity": parsed.get("complexity", "medium")
                },
                "estimated_time": estimated_time,
                "message": f"Ready to design protein using {parsed['design_mode']} mode with {parsed['diffusion_steps']} diffusion steps. Please confirm parameters."
            }
            
        except Exception as e:
            logger.error(f"Error processing design request: {e}")
            return {
                "error": str(e),
                "action": "error"
            }
    
    def _estimate_time(self, diffusion_steps: int, complexity: str = "medium") -> str:
        """Estimate design time based on parameters"""
        if diffusion_steps <= 10:
            base_time = "1-3 minutes"
        elif diffusion_steps <= 20:
            base_time = "3-8 minutes"
        elif diffusion_steps <= 50:
            base_time = "8-15 minutes"
        else:
            base_time = "15-30 minutes"
        
        if complexity == "high":
            base_time = base_time.replace("minutes", "minutes (complex)")
        elif complexity == "low":
            base_time = base_time.replace("minutes", "minutes (simple)")
        
        return base_time
    
    def _resolve_pdb_content(self, parameters: Dict[str, Any], user_id: Optional[str] = None) -> Optional[str]:
        """
        Resolve PDB content from multiple sources with priority:
        1. uploadId (uploaded file) - highest priority
        2. pdb_id (PDB ID) - fetch from RCSB
        3. input_pdb (raw content) - use directly
        
        Args:
            parameters: Design parameters containing PDB source info
            
        Returns:
            PDB content string or None if no PDB source provided
        """
        # Priority 1: Check for uploaded file
        upload_id = parameters.get("uploadId") or parameters.get("upload_file_id")
        if upload_id:
            try:
                logger.info(f"Attempting to resolve PDB from uploadId: {upload_id}, user_id: {user_id}")
                # Use user_id parameter passed to this function (from job_data)
                metadata = get_uploaded_pdb(upload_id, user_id=user_id)
                logger.info(f"get_uploaded_pdb returned: {metadata is not None}, has absolute_path: {metadata and 'absolute_path' in metadata if metadata else False}")
                if metadata and metadata.get("absolute_path"):
                    pdb_path = Path(metadata["absolute_path"])
                    logger.info(f"PDB file path: {pdb_path}, exists: {pdb_path.exists()}")
                    if pdb_path.exists():
                        pdb_content = pdb_path.read_text()
                        if pdb_content and pdb_content.strip():
                            logger.info(f"Successfully retrieved PDB from uploaded file: {upload_id} ({len(pdb_content)} chars)")
                            return pdb_content
                        else:
                            logger.warning(f"Uploaded PDB file is empty: {metadata.get('absolute_path')}")
                    else:
                        logger.warning(f"Uploaded PDB file not found at path: {metadata.get('absolute_path')}")
                else:
                    logger.warning(f"Uploaded PDB metadata not found for ID: {upload_id}, user_id: {user_id}")
            except Exception as e:
                logger.error(f"Error retrieving uploaded PDB {upload_id}: {e}", exc_info=True)
                # Fall through to next priority
        
        # Priority 2: Check for PDB ID
        pdb_id = parameters.get("pdb_id")
        if pdb_id:
            try:
                rfdiffusion_client = self._get_rfdiffusion_client()
                pdb_content = rfdiffusion_client.fetch_pdb_from_id(pdb_id)
                logger.info(f"Fetched PDB from RCSB: {pdb_id}")
                return pdb_content
            except Exception as e:
                logger.error(f"Error fetching PDB {pdb_id} from RCSB: {e}")
                # Fall through to next priority
        
        # Priority 3: Check for raw input_pdb content
        input_pdb = parameters.get("input_pdb")
        if input_pdb and input_pdb.strip():
            logger.info("Using provided input_pdb content")
            return input_pdb
        
        # No PDB source found
        return None
    
    async def submit_design_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit design job to RFdiffusion API
        
        Args:
            job_data: Job parameters from frontend
            
        Returns:
            Dictionary with job status and result
        """
        job_id = job_data.get("jobId")
        parameters = job_data.get("parameters", {})
        user_id = job_data.get("userId")

        if user_id and job_id:
            self.job_owners[job_id] = str(user_id)
        
        if not job_id:
            return {
                "status": "error",
                "error": "Missing job ID"
            }
        
        try:
            # Initialize RFdiffusion client
            try:
                rfdiffusion_client = self._get_rfdiffusion_client()
            except ValueError as config_error:
                # Configuration error (missing API key, etc.)
                self.active_jobs[job_id] = "error"
                return {
                    "status": "error",
                    "error": str(config_error)
                }
            
            # Create progress callback
            def progress_callback(message: str, progress: float):
                # In a real implementation, you'd send this to the frontend
                # via WebSocket or similar real-time mechanism
                logger.info(f"Job {job_id} progress: {progress}% - {message}")
            
            # Start the design job
            self.active_jobs[job_id] = "running"
            
            # Resolve PDB content from multiple sources
            logger.info(f"Resolving PDB content for job {job_id}, parameters keys: {list(parameters.keys())}, user_id: {user_id}")
            logger.info(f"Parameters uploadId: {parameters.get('uploadId')}, upload_file_id: {parameters.get('upload_file_id')}, pdb_id: {parameters.get('pdb_id')}")
            pdb_content = self._resolve_pdb_content(parameters, user_id=user_id)
            design_mode = parameters.get("design_mode", "unconditional")
            logger.info(f"PDB resolution result: content_length={len(pdb_content) if pdb_content else 0}, design_mode={design_mode}, has_content={bool(pdb_content)}")
            
            # Prepare parameters for RFdiffusion client
            # If PDB content was resolved, pass it as input_pdb
            # Remove uploadId and pdb_id from parameters since we've resolved the content
            client_params = {**parameters}
            
            # Ensure design_mode is always included
            client_params["design_mode"] = design_mode
            
            # Remove empty string values for PDB-related fields
            for key in ["uploadId", "upload_file_id", "pdb_id", "input_pdb"]:
                if key in client_params and (client_params[key] == "" or client_params[key] is None):
                    client_params.pop(key, None)
            
            if pdb_content:
                client_params["input_pdb"] = pdb_content
                logger.info(f"Set input_pdb in client_params, length: {len(pdb_content)}")
                # Remove source identifiers since we have the content
                client_params.pop("uploadId", None)
                client_params.pop("upload_file_id", None)
                client_params.pop("pdb_id", None)
            elif design_mode != "unconditional":
                # For non-unconditional designs, PDB is required
                logger.warning(f"No PDB content resolved for job {job_id}, design_mode: {design_mode}")
                pdb_error = {
                    "error": "PDB template is required for motif_scaffolding and partial_diffusion modes. Please provide a PDB ID, upload a file, or use unconditional design mode.",
                    "errorCode": "MISSING_PDB_TEMPLATE",
                    "originalError": f"No PDB content resolved for design_mode={design_mode}",
                    "parameters": parameters,
                }
                self.active_jobs[job_id] = "error"
                self.job_results[job_id] = pdb_error
                return {
                    "status": "error",
                    "error": pdb_error["error"],
                    "errorCode": "MISSING_PDB_TEMPLATE",
                    "originalError": pdb_error["originalError"],
                }
            else:
                # For unconditional design without PDB, ensure all PDB-related params are removed
                logger.info(f"Unconditional design without PDB - removed all PDB-related params. Remaining keys: {list(client_params.keys())}")
                client_params.pop("uploadId", None)
                client_params.pop("upload_file_id", None)
                client_params.pop("pdb_id", None)
                client_params.pop("input_pdb", None)
            
            # Submit to RFdiffusion API
            try:
                logger.info(f"Submitting RFdiffusion design job {job_id} with params: {list(client_params.keys())}, design_mode={design_mode}")
                # Debug: Log client params being sent to NVIDIA API
                print("=" * 80)
                print(f"[RFdiffusion Handler] ===== CLIENT PARAMS TO NVIDIA API ======")
                print(f"[RFdiffusion Handler] Job ID: {job_id}")
                print(f"[RFdiffusion Handler] Design mode: {design_mode}")
                print(f"[RFdiffusion Handler] Client params keys: {list(client_params.keys())}")
                for key, value in client_params.items():
                    if key == "input_pdb" and isinstance(value, str):
                        print(f"[RFdiffusion Handler]   {key}: {type(value).__name__} (length: {len(value)})")
                    elif isinstance(value, (dict, list)):
                        print(f"[RFdiffusion Handler]   {key}: {type(value).__name__} = {value}")
                    else:
                        print(f"[RFdiffusion Handler]   {key}: {type(value).__name__} = {repr(value)}")
                print("=" * 80)
                result = await rfdiffusion_client.submit_design_request(
                    progress_callback=progress_callback,
                    **client_params
                )
            except Exception as e:
                logger.error(f"Error in submit_design_request for job {job_id}: {e}", exc_info=True)
                self.active_jobs[job_id] = "error"
                submit_error = {
                    "error": f"Failed to submit design request: {str(e)}",
                    "errorCode": "SUBMIT_FAILED",
                    "originalError": str(e),
                    "parameters": parameters,
                }
                self.job_results[job_id] = submit_error
                return {
                    "status": "error",
                    "error": submit_error["error"],
                    "errorCode": "SUBMIT_FAILED",
                    "originalError": str(e),
                }
            
            # Check for various error statuses
            if result.get("status") == "exception" or result.get("status") == "request_failed":
                self.active_jobs[job_id] = "error"
                error_msg = result.get("error", "Design failed")
                error_details = result.get("details", "")
                
                logger.error(f"RFdiffusion API returned error status: {error_msg}")
                if error_details:
                    logger.error(f"Error details: {error_details}")
                
                # Parse HTTP error responses for better user messages
                original_error = error_msg  # Preserve the raw API error
                user_friendly_error = error_msg
                error_code = "DESIGN_FAILED"
                
                if "HTTP 422" in error_msg or "422" in error_msg:
                    error_code = "VALIDATION_ERROR"
                    # Extract detail from JSON response if available
                    try:
                        if "detail" in error_msg.lower():
                            json_start = error_msg.find("{")
                            if json_start != -1:
                                json_str = error_msg[json_start:]
                                error_data = json.loads(json_str)
                                detail = error_data.get("detail", error_msg)
                                original_error = detail
                                logger.error(f"RFdiffusion API validation error: {detail}")
                    except Exception:
                        pass
                    # Keep the original error in the message for clarity
                    user_friendly_error = f"Validation error: {original_error}. Please check that your hotspot residues exist in the PDB file and that the PDB file contains the expected chains and residues."
                elif "401" in error_msg or "403" in error_msg:
                    error_code = "AUTH_ERROR"
                    user_friendly_error = "Authentication failed. Please check your NVIDIA API key configuration."
                elif "500" in error_msg or "502" in error_msg or "503" in error_msg:
                    error_code = "SERVICE_UNAVAILABLE"
                    user_friendly_error = "The RFdiffusion service is temporarily unavailable. Please try again later."
                
                # Store error in job_results so status endpoint can return it
                error_result = {
                    "error": user_friendly_error,
                    "errorCode": error_code,
                    "originalError": original_error,
                    "parameters": parameters,
                }
                self.job_results[job_id] = error_result
                
                return {
                    "status": "error",
                    "error": user_friendly_error,
                    "errorCode": error_code,
                    "originalError": original_error,
                }
            
            if result.get("status") == "completed":
                # Extract PDB content
                pdb_content = rfdiffusion_client.extract_pdb_from_result(result["data"])
                
                if pdb_content:
                    # Save PDB file using user-scoped storage
                    user_id = job_data.get("userId")
                    logger.info(f"[RFdiffusion Handler] Saving file for job {job_id}, userId from job_data: {user_id}")
                    if not user_id:
                        logger.error(f"[RFdiffusion Handler] CRITICAL: No userId provided in job_data! Keys: {list(job_data.keys())}")
                        logger.warning("[RFdiffusion Handler] No userId provided, cannot save file with user isolation")
                        user_id = "system"  # Fallback for backward compatibility
                    
                    logger.info(f"[RFdiffusion Handler] Using user_id: {user_id} for file save")
                    filename = f"rfdiffusion_{job_id}.pdb"
                    filepath = save_result_file(
                        user_id=user_id,
                        file_id=job_id,
                        file_type="rfdiffusion",
                        filename=filename,
                        content=pdb_content.encode("utf-8"),
                        job_id=job_id,
                        metadata={
                            "parameters": parameters,
                            "design_mode": parameters.get("design_mode", "unknown"),
                        },
                    )
                    
                    # Associate file with session if session_id provided
                    session_id = job_data.get("sessionId")
                    logger.info(f"[RFdiffusion Handler] Session ID from job_data: {session_id} (type: {type(session_id).__name__})")
                    if session_id and user_id:
                        try:
                            logger.info(f"[RFdiffusion Handler] Associating file with session: session_id={session_id}, file_id={job_id}, filepath={filepath}")
                            associate_file_with_session(
                                session_id=str(session_id),
                                file_id=job_id,
                                user_id=user_id,
                                file_type="rfdiffusion",
                                file_path=filepath,
                                filename=filename,
                                size=len(pdb_content),
                                job_id=job_id,
                                metadata={
                                    "parameters": parameters,
                                    "design_mode": parameters.get("design_mode", "unknown"),
                                },
                            )
                            logger.info(f"[RFdiffusion Handler] Successfully associated file {job_id} with session {session_id}")
                        except Exception as e:
                            logger.error(f"Failed to associate RFdiffusion file with session: {e}", exc_info=True)
                    else:
                        logger.warning(f"[RFdiffusion Handler] No session_id or userId provided, file {job_id} will not be associated with any session")
                    
                    self.active_jobs[job_id] = "completed"
                    
                    # Store result data for status endpoint
                    result_data = {
                        "pdbContent": pdb_content,
                        "fileId": job_id,  # File ID for frontend to load from server
                        "filename": filename,
                        "filepath": filepath,
                        "metadata": {
                            "job_id": job_id,
                            "parameters": parameters,
                            "design_mode": parameters.get("design_mode", "unknown")
                        }
                    }
                    self.job_results[job_id] = result_data
                    
                    return {
                        "status": "success",
                        "data": result_data
                    }
                else:
                    self.active_jobs[job_id] = "error"
                    no_pdb_error = {
                        "error": "No PDB content in API response. The design may have succeeded but the result could not be parsed.",
                        "errorCode": "NO_PDB_CONTENT",
                        "originalError": "No PDB content in API response",
                        "parameters": parameters,
                    }
                    self.job_results[job_id] = no_pdb_error
                    return {
                        "status": "error",
                        "error": no_pdb_error["error"],
                        "errorCode": "NO_PDB_CONTENT",
                    }
            else:
                self.active_jobs[job_id] = "error"
                fallback_error = result.get("error", "Design failed")
                error_result = {
                    "error": fallback_error,
                    "errorCode": "DESIGN_FAILED",
                    "originalError": fallback_error,
                    "parameters": parameters,
                }
                self.job_results[job_id] = error_result
                return {
                    "status": "error",
                    "error": fallback_error,
                    "errorCode": "DESIGN_FAILED",
                }
                
        except Exception as e:
            logger.error(f"RFdiffusion job {job_id} failed: {e}")
            self.active_jobs[job_id] = "error"
            exception_error = {
                "error": str(e),
                "errorCode": "INTERNAL_ERROR",
                "originalError": str(e),
                "parameters": parameters,
            }
            self.job_results[job_id] = exception_error
            return {
                "status": "error",
                "error": str(e),
                "errorCode": "INTERNAL_ERROR",
            }
    
    def get_job_status(self, job_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get status of a running job"""
        status = self.active_jobs.get(job_id, "not_found")
        owner_id = self.job_owners.get(job_id)
        if user_id and status != "not_found" and owner_id != user_id:
            return {
                "job_id": job_id,
                "status": "not_found"
            }

        response = {
            "job_id": job_id,
            "status": status
        }
        
        # If job is completed, include result data
        if status == "completed" and job_id in self.job_results:
            response["data"] = self.job_results[job_id]
        elif status == "error":
            # Include full error details if available
            if job_id in self.job_results:
                error_data = self.job_results[job_id]
                response["error"] = error_data.get("error", "Job failed")
                response["errorCode"] = error_data.get("errorCode", "UNKNOWN_ERROR")
                response["originalError"] = error_data.get("originalError", "")
                response["parameters"] = error_data.get("parameters", {})
        elif status == "not_found":
            # Check if result file exists in storage (job may have completed before restart)
            try:
                from ...domain.storage.file_access import get_file_metadata
                file_metadata = get_file_metadata(job_id, user_id=user_id) if user_id else get_file_metadata(job_id)
                if file_metadata and file_metadata.get("file_type") == "rfdiffusion":
                    # Result file exists, try to load it
                    from pathlib import Path
                    base_dir = Path(__file__).parent.parent.parent
                    stored_path = file_metadata.get("stored_path")
                    if stored_path:
                        file_path = base_dir / stored_path
                        if file_path.exists():
                            # Read PDB content
                            pdb_content = file_path.read_text(encoding="utf-8")
                            metadata = file_metadata.get("metadata", {})
                            if isinstance(metadata, str):
                                import json
                                try:
                                    metadata = json.loads(metadata)
                                except:
                                    metadata = {}
                            
                            response["status"] = "completed"
                            response["data"] = {
                                "pdbContent": pdb_content,
                                "fileId": job_id,
                                "filename": file_metadata.get("original_filename", f"rfdiffusion_{job_id}.pdb"),
                                "filepath": stored_path,
                                "metadata": metadata
                            }
                            # Store in job_results for future requests
                            self.job_results[job_id] = response["data"]
            except Exception as e:
                logger.debug(f"Could not recover RFdiffusion job {job_id} from storage: {e}")
                # Keep status as "not_found"
        
        return response
    
    def cancel_job(self, job_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Cancel a running job"""
        owner_id = self.job_owners.get(job_id)
        if user_id and owner_id != user_id:
            return {
                "job_id": job_id,
                "status": "not_found"
            }

        if job_id in self.active_jobs:
            self.active_jobs[job_id] = "cancelled"
            return {
                "job_id": job_id,
                "status": "cancelled"
            }
        else:
            return {
                "job_id": job_id,
                "status": "not_found"
            }


# Global handler instance
rfdiffusion_handler = RFdiffusionHandler()


# Example usage
async def test_rfdiffusion_handler():
    """Test the RFdiffusion handler"""
    handler = RFdiffusionHandler()
    
    # Test request processing
    test_requests = [
        "design a protein",
        "design protein using PDB:1R42 with hotspots A50,A51,A52",
        "design 100-150 residue protein with 20 steps",
        "create complex protein design with contigs A20-60/0 50-100",
    ]
    
    for request in test_requests:
        print(f"\nProcessing: {request}")
        result = await handler.process_design_request(request)
        print(f"Result: {json.dumps(result, indent=2)}")


if __name__ == "__main__":
    asyncio.run(test_rfdiffusion_handler())