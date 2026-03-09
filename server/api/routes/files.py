"""File upload and management API endpoints."""

import json
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response

try:
    from ...domain.storage.pdb_storage import save_uploaded_pdb, get_uploaded_pdb, filter_pdb_content
    from ...domain.storage.file_access import list_user_files, verify_file_ownership, get_file_metadata, get_user_file_path
    from ...tools.smiles_converter import smiles_to_structure
    from ...database.db import get_db
    from ...infrastructure.utils import log_line
    from ...api.middleware.auth import get_current_user
    from ...api.limiter import limiter, DEBUG_API
except ImportError:
    from domain.storage.pdb_storage import save_uploaded_pdb, get_uploaded_pdb, filter_pdb_content
    from domain.storage.file_access import list_user_files, verify_file_ownership, get_file_metadata, get_user_file_path
    from tools.smiles_converter import smiles_to_structure
    from database.db import get_db
    from infrastructure.utils import log_line
    from api.middleware.auth import get_current_user
    from api.limiter import limiter, DEBUG_API

router = APIRouter()


@router.post("/api/upload/pdb")
@limiter.limit("20/minute")
async def upload_pdb(
    request: Request,
    file: UploadFile = File(...),
    user: Dict[str, Any] = Depends(get_current_user),
):
    _ = request
    try:
        contents = await file.read()
        user_id = user.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found")
        metadata = save_uploaded_pdb(file.filename, contents, user_id)
        log_line("pdb_upload_success", {
            "filename": file.filename,
            "file_id": metadata["file_id"],
            "size": metadata.get("size"),
            "chains": metadata.get("chains"),
        })
        return {
            "status": "success",
            "message": "File uploaded",
            "file_info": {
                "filename": metadata.get("filename"),
                "file_id": metadata.get("file_id"),
                "file_url": f"/api/upload/pdb/{metadata.get('file_id')}",
                "file_path": metadata.get("stored_path"),
                "size": metadata.get("size"),
                "atoms": metadata.get("atoms"),
                "chains": metadata.get("chains", []),
                "chain_residue_counts": metadata.get("chain_residue_counts", {}),
                "total_residues": metadata.get("total_residues"),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        log_line("pdb_upload_failed", {"error": str(e), "trace": traceback.format_exc()})
        raise HTTPException(status_code=500, detail="Failed to upload PDB file")


@router.post("/api/upload/pdb/from-content")
@limiter.limit("30/minute")
async def upload_pdb_from_content(
    request: Request,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Store PDB content from message results and return file_id for clean API URLs."""
    _ = request
    try:
        body = await request.json()
        pdb_content = body.get("pdbContent") or body.get("pdb_content")
        filename = body.get("filename", "structure.pdb")
        if not pdb_content:
            raise HTTPException(status_code=400, detail="pdbContent is required")
        if not filename.lower().endswith(".pdb"):
            filename = f"{filename}.pdb" if not filename.endswith(".pdb") else "structure.pdb"
        user_id = user.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found")
        contents = pdb_content.encode("utf-8") if isinstance(pdb_content, str) else pdb_content
        metadata = save_uploaded_pdb(filename, contents, user_id)
        return {
            "status": "success",
            "message": "PDB stored",
            "file_info": {
                "filename": metadata.get("filename"),
                "file_id": metadata.get("file_id"),
                "file_url": f"/api/upload/pdb/{metadata.get('file_id')}",
                "atoms": metadata.get("atoms"),
                "chains": metadata.get("chains", []),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        log_line("pdb_from_content_failed", {"error": str(e), "trace": traceback.format_exc()})
        raise HTTPException(status_code=500, detail="Failed to store PDB content")


@router.get("/api/upload/pdb/{file_id}")
@limiter.limit("30/minute")
async def download_uploaded_pdb(request: Request, file_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    _ = request
    metadata = get_uploaded_pdb(file_id, user["id"])
    if not metadata:
        raise HTTPException(status_code=404, detail="Uploaded file not found")
    filename = metadata.get("filename") or f"{file_id}.pdb"
    media_type = "chemical/x-mdl-sdfile" if str(filename).lower().endswith(".sdf") else "chemical/x-pdb"
    return FileResponse(metadata["absolute_path"], media_type=media_type, filename=filename)


@router.get("/api/upload/pdb/{file_id}/filtered")
@limiter.limit("30/minute")
async def download_filtered_uploaded_pdb(
    request: Request,
    file_id: str,
    chains: Optional[str] = None,
    include_waters: bool = True,
    include_ligands: bool = True,
    user: Dict[str, Any] = Depends(get_current_user),
):
    _ = request
    metadata = get_uploaded_pdb(file_id, user["id"])
    if not metadata:
        raise HTTPException(status_code=404, detail="Uploaded file not found")

    source_path = metadata.get("absolute_path")
    if not source_path:
        raise HTTPException(status_code=404, detail="Uploaded file path is missing")

    try:
        source_text = Path(str(source_path)).read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read source PDB: {exc}")

    selected_chains = [c.strip() for c in (chains or "").split(",") if c.strip()]
    filtered_content = filter_pdb_content(
        source_text,
        chains=selected_chains,
        include_waters=include_waters,
        include_ligands=include_ligands,
    )

    has_atoms = any(
        line.startswith("ATOM") or line.startswith("HETATM")
        for line in filtered_content.splitlines()
    )
    if not has_atoms:
        raise HTTPException(status_code=400, detail="Filter produced an empty structure")

    original_filename = str(metadata.get("filename") or f"{file_id}.pdb")
    base_name = Path(original_filename).stem
    chain_suffix = f"chains-{'-'.join(selected_chains)}" if selected_chains else "all-chains"
    waters_suffix = "waters-on" if include_waters else "waters-off"
    ligands_suffix = "ligands-on" if include_ligands else "ligands-off"
    download_filename = f"{base_name}_{chain_suffix}_{waters_suffix}_{ligands_suffix}_filtered.pdb"

    return Response(
        content=filtered_content,
        media_type="chemical/x-pdb",
        headers={"Content-Disposition": f'attachment; filename="{download_filename}"'},
    )


@router.post("/api/smiles/to-structure")
@limiter.limit("30/minute")
async def smiles_to_structure_endpoint(
    request: Request,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Convert SMILES to 3D structure (PDB or SDF) for loading in the MolStar viewer."""
    try:
        body = await request.json()
        smiles = (body.get("smiles") or "").strip()
        fmt = (body.get("format") or "sdf").lower()
        if fmt not in ("pdb", "sdf"):
            fmt = "sdf"
        if not smiles:
            return JSONResponse(
                status_code=400,
                content={
                    "userMessage": "SMILES string is required.",
                    "technicalMessage": "Request body must include a non-empty 'smiles' field.",
                },
            )
        content, filename = smiles_to_structure(smiles, fmt)
        return {"content": content, "filename": filename, "format": fmt}
    except ValueError as e:
        log_line("smiles_conversion_validation_failed", {"error": str(e)})
        return JSONResponse(
            status_code=400,
            content={
                "userMessage": str(e) or "Invalid SMILES or conversion failed.",
                "technicalMessage": str(e),
            },
        )
    except RuntimeError as e:
        log_line("smiles_conversion_runtime_failed", {"error": str(e)})
        return JSONResponse(
            status_code=503,
            content={
                "userMessage": "SMILES conversion is not available (RDKit not installed).",
                "technicalMessage": str(e),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        log_line("smiles_conversion_failed", {"error": str(e), "trace": traceback.format_exc()})
        return JSONResponse(
            status_code=500,
            content={
                "userMessage": "Failed to convert SMILES to structure.",
                "technicalMessage": str(e),
            },
        )


@router.get("/api/files")
@limiter.limit("30/minute")
async def get_user_files_endpoint(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    """List all files for the current user."""
    _ = request
    try:
        log_line("user_files_request", {"user_id": user["id"]})
        base_dir = Path(__file__).parent.parent.parent
        all_files = []

        user_files = list_user_files(user["id"])
        log_line("user_files_raw", {"user_id": user["id"], "count": len(user_files)})

        for file_entry in user_files:
            file_type = file_entry.get("file_type", "")
            file_id = file_entry.get("id", "")
            stored_path_str = file_entry.get("stored_path", "")
            filename = file_entry.get("original_filename", f"{file_id}")

            log_line("processing_file", {
                "file_id": file_id,
                "file_type": file_type,
                "stored_path": stored_path_str,
                "filename": filename,
            })

            if stored_path_str:
                file_path = base_dir / stored_path_str
                file_exists = file_path.exists()
                log_line("file_path_check", {
                    "file_id": file_id,
                    "stored_path": stored_path_str,
                    "absolute_path": str(file_path),
                    "exists": file_exists,
                })

                if file_exists:
                    if file_type == "upload":
                        download_url = f"/api/upload/pdb/{file_id}"
                    elif file_type == "proteinmpnn":
                        download_url = f"/api/proteinmpnn/result/{file_id}"
                    elif file_type == "openfold2":
                        download_url = f"/api/openfold2/result/{file_id}"
                    else:
                        download_url = f"/api/files/{file_id}/download"

                    metadata = file_entry.get("metadata", {})
                    if isinstance(metadata, str):
                        try:
                            metadata = json.loads(metadata)
                        except json.JSONDecodeError:
                            metadata = {}

                    file_size = file_entry.get("size", 0)
                    if file_size == 0:
                        try:
                            file_size = file_path.stat().st_size
                        except OSError:
                            file_size = 0

                    all_files.append({
                        "file_id": file_id,
                        "type": file_type,
                        "filename": filename,
                        "file_path": stored_path_str,
                        "size": file_size,
                        "download_url": download_url,
                        "metadata": metadata,
                    })
                else:
                    log_line("file_not_found", {"file_id": file_id, "expected_path": str(file_path)})

        log_line("user_files_loaded", {"user_id": user["id"], "file_count": len(all_files)})
        return {"status": "success", "files": all_files}
    except Exception as e:
        log_line("user_files_list_failed", {"error": str(e), "trace": traceback.format_exc(), "user_id": user["id"]})
        content = {"error": "Failed to list user files"}
        if DEBUG_API:
            content["detail"] = str(e)
        return JSONResponse(status_code=500, content=content)


@router.get("/api/files/{file_id}/download")
@limiter.limit("30/minute")
async def download_user_file(request: Request, file_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    """Download a user file. Verifies ownership."""
    _ = request
    try:
        file_path = get_user_file_path(file_id, user["id"])
        file_metadata = get_file_metadata(file_id, user["id"])
        filename = file_metadata.get("original_filename", f"{file_id}.pdb") if file_metadata else f"{file_id}.pdb"
        media_type = "chemical/x-pdb" if filename.lower().endswith(".pdb") else "application/octet-stream"
        log_line("file_downloaded", {"file_id": file_id, "user_id": user["id"], "path": str(file_path)})
        return FileResponse(file_path, media_type=media_type, filename=filename)
    except HTTPException:
        raise
    except Exception as e:
        log_line("file_download_failed", {"error": str(e), "trace": traceback.format_exc()})
        raise HTTPException(status_code=500, detail="Failed to download file")


@router.get("/api/files/{file_id}")
@limiter.limit("30/minute")
async def get_user_file_content(request: Request, file_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    """Get file content as JSON (for editor/viewer). Verifies ownership."""
    _ = request
    try:
        file_path = get_user_file_path(file_id, user["id"])
        file_metadata = get_file_metadata(file_id, user["id"])
        if not file_metadata:
            raise HTTPException(status_code=404, detail="File not found")

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            import base64
            content = base64.b64encode(file_path.read_bytes()).decode("utf-8")
            return {
                "status": "success",
                "file_id": file_id,
                "filename": file_metadata.get("original_filename", f"{file_id}.pdb"),
                "content": content,
                "encoding": "base64",
                "type": file_metadata.get("file_type", "unknown"),
            }

        log_line("file_content_accessed", {"file_id": file_id, "user_id": user["id"], "path": str(file_path)})
        return {
            "status": "success",
            "file_id": file_id,
            "filename": file_metadata.get("original_filename", f"{file_id}.pdb"),
            "content": content,
            "type": file_metadata.get("file_type", "unknown"),
        }
    except HTTPException:
        raise
    except Exception as e:
        log_line("file_content_failed", {"error": str(e), "trace": traceback.format_exc()})
        raise HTTPException(status_code=500, detail="Failed to read file content")


@router.delete("/api/files/{file_id}")
@limiter.limit("10/minute")
async def delete_user_file(request: Request, file_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    """Delete a user file. Verifies ownership."""
    _ = request
    try:
        if not verify_file_ownership(file_id, user["id"]):
            raise HTTPException(status_code=403, detail="File not found or access denied")

        file_metadata = get_file_metadata(file_id, user["id"])
        if not file_metadata:
            raise HTTPException(status_code=404, detail="File not found")

        base_dir = Path(__file__).parent.parent.parent
        stored_path = file_metadata.get("stored_path")

        if stored_path:
            file_path = base_dir / stored_path
            if file_path.exists():
                file_path.unlink()
                log_line("file_deleted", {"file_id": file_id, "user_id": user["id"], "path": str(file_path)})

        with get_db() as conn:
            conn.execute("DELETE FROM user_files WHERE id = ? AND user_id = ?", (file_id, user["id"]))
            conn.execute("DELETE FROM session_files WHERE file_id = ? AND user_id = ?", (file_id, user["id"]))

        return {"status": "success", "message": "File deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        log_line("file_delete_failed", {"error": str(e), "trace": traceback.format_exc(), "file_id": file_id, "user_id": user["id"]})
        content = {"error": "Failed to delete file"}
        if DEBUG_API:
            content["detail"] = str(e)
        return JSONResponse(status_code=500, content=content)
