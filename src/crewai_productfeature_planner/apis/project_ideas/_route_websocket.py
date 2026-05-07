"""WebSocket endpoint for real-time idea updates.

Provides ``WS /ws/ideas/{idea_id}`` for subscribing to:
- status changes (draft → active → in_progress → completed)
- flow progress updates (sections, iterations)
- feature completion changes (from Jira webhooks)
- design URL updates
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from crewai_productfeature_planner.mongodb._tenant import TenantContext
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

ws_router = APIRouter()

# ── Connection hub ─────────────────────────────────────────────

# idea_id → set of connected WebSockets
_idea_connections: dict[str, set[WebSocket]] = {}
_lock = asyncio.Lock()


async def _register(idea_id: str, ws: WebSocket) -> None:
    async with _lock:
        _idea_connections.setdefault(idea_id, set()).add(ws)


async def _unregister(idea_id: str, ws: WebSocket) -> None:
    async with _lock:
        conns = _idea_connections.get(idea_id)
        if conns:
            conns.discard(ws)
            if not conns:
                del _idea_connections[idea_id]


async def broadcast_idea_event(idea_id: str, event: dict[str, Any]) -> None:
    """Send event to all WebSocket clients subscribed to idea_id."""
    async with _lock:
        conns = _idea_connections.get(idea_id)
        if not conns:
            return
        dead: list[WebSocket] = []
        payload = json.dumps(event, default=str)
        for ws in conns:
            try:
                await ws.send_text(payload)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            conns.discard(ws)
        if not conns:
            _idea_connections.pop(idea_id, None)


def broadcast_idea_sync(idea_id: str, event: dict[str, Any]) -> None:
    """Thread-safe broadcast for idea events — callable from sync code."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(broadcast_idea_event(idea_id, event))
    except RuntimeError:
        # No running loop — skip (tests, CLI)
        pass


@ws_router.websocket("/ws/ideas/{idea_id}")
async def idea_websocket(
    websocket: WebSocket,
    idea_id: str,
    token: str = Query(default=""),
):
    """WebSocket for real-time idea updates.

    Authenticates via JWT token query param, then streams events.
    """
    from crewai_productfeature_planner.apis.prd._route_websocket import (
        _validate_ws_token,
    )
    from crewai_productfeature_planner.mongodb.ideas.repository import get_idea

    # Authenticate
    user = await _validate_ws_token(token)

    if not user:
        await websocket.close(code=4001, reason="Authentication required")
        return

    tenant = TenantContext.from_user(user)

    # Verify idea exists and is accessible
    doc = get_idea(idea_id=idea_id, tenant=tenant)
    if not doc:
        await websocket.close(code=4004, reason="Idea not found")
        return

    await websocket.accept()
    await _register(idea_id, websocket)

    logger.info(
        "[IdeaWS] Client connected idea_id=%s user=%s",
        idea_id, user.get("user_id", "?"),
    )

    # Send initial state
    await websocket.send_text(json.dumps({
        "event": "connected",
        "data": {
            "idea_id": idea_id,
            "status": doc.get("status"),
            "overall_completion": doc.get("overall_completion", 0.0),
            "active_run_id": doc.get("active_run_id"),
        },
    }))

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            msg_type = msg.get("type", "")

            if msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            else:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                }))
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.debug("[IdeaWS] Connection error idea_id=%s", idea_id, exc_info=True)
    finally:
        await _unregister(idea_id, websocket)
        logger.info("[IdeaWS] Client disconnected idea_id=%s", idea_id)
