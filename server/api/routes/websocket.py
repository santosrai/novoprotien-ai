#!/usr/bin/env python3
"""
WebSocket routes for real-time job updates.
"""

import json
import logging
from typing import Dict, Set, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.routing import APIRouter

from ...infrastructure.auth import verify_token
from ...domain.user.service import get_user_by_id

logger = logging.getLogger(__name__)

router = APIRouter()


class WebSocketManager:
    """Manages WebSocket connections for job updates"""
    
    def __init__(self):
        # Map job_id -> set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, job_id: str):
        """Connect a WebSocket for a specific job"""
        await websocket.accept()
        if job_id not in self.active_connections:
            self.active_connections[job_id] = set()
        self.active_connections[job_id].add(websocket)
        logger.info(f"WebSocket connected for job {job_id} (total: {len(self.active_connections.get(job_id, []))})")
    
    def disconnect(self, websocket: WebSocket, job_id: str):
        """Disconnect a WebSocket"""
        if job_id in self.active_connections:
            self.active_connections[job_id].discard(websocket)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]
        logger.info(f"WebSocket disconnected for job {job_id}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send message to a specific WebSocket"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send WebSocket message: {e}")
    
    async def broadcast_to_job(self, job_id: str, message: dict):
        """Broadcast message to all connections for a job"""
        if job_id not in self.active_connections:
            return
        
        disconnected = set()
        for connection in self.active_connections[job_id]:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket for job {job_id}: {e}")
                disconnected.add(connection)
        
        # Remove disconnected connections
        for connection in disconnected:
            self.disconnect(connection, job_id)


# Global WebSocket manager instance
websocket_manager = WebSocketManager()


def _extract_bearer_token(websocket: WebSocket) -> Optional[str]:
    token = websocket.query_params.get("token")
    if token:
        return token

    auth_header = websocket.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return None


async def _authenticate_websocket(websocket: WebSocket) -> Optional[Dict[str, Any]]:
    token = _extract_bearer_token(websocket)
    if not token:
        await websocket.close(code=1008, reason="Authentication required")
        return None

    try:
        payload = verify_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("Missing subject claim")

        user = get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        is_active = user.get("is_active")
        try:
            is_active_int = int(is_active) if is_active is not None else 0
        except (ValueError, TypeError):
            is_active_int = 0
        if is_active_int != 1 and is_active is not True:
            raise ValueError("Inactive user")

        return user
    except Exception as exc:
        logger.warning("WebSocket auth failed for job updates: %s", exc)
        await websocket.close(code=1008, reason="Invalid authentication token")
        return None


@router.websocket("/api/ws/jobs/{job_id}")
async def websocket_job_updates(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for real-time job updates
    
    Args:
        websocket: WebSocket connection
        job_id: Job identifier to subscribe to
    """
    user = await _authenticate_websocket(websocket)
    if not user:
        return
    
    try:
        # Send initial status
        try:
            from ...agents.handlers.alphafold import alphafold_handler
            status = alphafold_handler.get_job_status(job_id, user_id=user.get("id"))
            if status.get("status") == "not_found":
                await websocket.close(code=1008, reason="Job not found or access denied")
                return
            await websocket_manager.connect(websocket, job_id)
            await websocket_manager.send_personal_message({
                "type": "status",
                "data": status
            }, websocket)
        except Exception as e:
            logger.error(f"Failed to get initial status for job {job_id}: {e}")
            await websocket.close(code=1011, reason="Failed to initialize job stream")
            return
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                data = await websocket.receive_text()
                # Handle ping/pong or other client messages if needed
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error for job {job_id}: {e}")
                break
    except WebSocketDisconnect:
        pass
    finally:
        websocket_manager.disconnect(websocket, job_id)
