"""WebSocket endpoint — real-time updates for project knowledge documents.

Provides ``WS /ws/projects/{project_id}/knowledge`` for server-to-client
push of document status changes, review completions, and unified summary
regenerations.

**Server → Client events:**

- ``knowledge.doc.updated`` — doc status changed or review completed
- ``knowledge.doc.deleted`` — doc removed
- ``knowledge.summary.updated`` — unified summary regenerated
- ``error`` — server-side processing error

**Client → Server messages:**

- ``{"event": "ping"}`` — keepalive; server responds ``{"event": "pong"}``
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from crewai_productfeature_planner.apis._ws_auth import validate_ws_token
from crewai_productfeature_planner.mongodb._tenant import TenantContext
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

knowledge_ws_router = APIRouter()

# project_id → set of connected WebSockets
_connections: dict[str, set[WebSocket]] = {}
_lock = asyncio.Lock()

_main_loop: asyncio.AbstractEventLoop | None = None


def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Called once during app startup to capture the main event loop."""
    global _main_loop  # noqa: PLW0603
    _main_loop = loop


# ── Room management ──────────────────────────────────────────────


async def _register(project_id: str, ws: WebSocket) -> None:
    async with _lock:
        _connections.setdefault(project_id, set()).add(ws)


async def _unregister(project_id: str, ws: WebSocket) -> None:
    async with _lock:
        conns = _connections.get(project_id)
        if conns:
            conns.discard(ws)
            if not conns:
                del _connections[project_id]


# ── Broadcast helpers ────────────────────────────────────────────


async def broadcast_knowledge(project_id: str, event: dict[str, Any]) -> None:
    """Send *event* to all WebSocket clients connected to *project_id*."""
    async with _lock:
        conns = _connections.get(project_id)
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
            _connections.pop(project_id, None)


def broadcast_knowledge_sync(project_id: str, event: dict[str, Any]) -> None:
    """Thread-safe broadcast — callable from synchronous background threads.

    Works correctly from both the main async thread and from
    ``ThreadPoolExecutor`` worker threads.
    """
    try:
        loop = asyncio.get_running_loop()
        future = asyncio.ensure_future(
            broadcast_knowledge(project_id, event), loop=loop,
        )
        future.add_done_callback(_log_broadcast_error)
        return
    except RuntimeError:
        pass

    loop = _main_loop
    if loop is not None and loop.is_running():
        asyncio.run_coroutine_threadsafe(
            broadcast_knowledge(project_id, event), loop,
        )
    else:
        logger.warning(
            "[KnowledgeWS] broadcast_sync: no usable event loop project=%s",
            project_id,
        )


def _log_broadcast_error(future: asyncio.Future) -> None:
    exc = future.exception()
    if exc:
        logger.warning("[KnowledgeWS] broadcast future failed: %s", exc)


# ── WebSocket endpoint ───────────────────────────────────────────


@knowledge_ws_router.websocket("/ws/projects/{project_id}/knowledge")
async def knowledge_websocket(
    websocket: WebSocket,
    project_id: str,
    token: str | None = Query(default=None),
):
    """WebSocket endpoint for real-time knowledge document updates.

    Authenticates via ``?token=`` query param (JWT access token).
    """
    await websocket.accept()

    user = await validate_ws_token(token)
    if not user:
        error_code = "TOKEN_MISSING" if not token else "TOKEN_EXPIRED"
        await websocket.send_text(json.dumps({
            "event": "auth_error",
            "data": {
                "code": error_code,
                "message": (
                    "Authentication failed — your token is expired or invalid. "
                    "Please refresh your access token and reconnect."
                ),
                "recoverable": True,
            },
        }))
        await websocket.close(code=4001)
        logger.warning(
            "[KnowledgeWS] Rejected — %s project=%s",
            error_code.lower(),
            project_id,
        )
        return

    await _register(project_id, websocket)
    logger.info("[KnowledgeWS] Client connected project=%s", project_id)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "event": "error",
                    "data": {"message": "Invalid JSON"},
                }))
                continue

            msg_event = msg.get("event") or msg.get("type", "")

            if msg_event == "ping":
                await websocket.send_text(json.dumps({"event": "pong"}))
            else:
                await websocket.send_text(json.dumps({
                    "event": "error",
                    "data": {"message": f"Unknown event: {msg_event}"},
                }))

    except WebSocketDisconnect:
        logger.info("[KnowledgeWS] Client disconnected project=%s", project_id)
    except Exception as exc:
        logger.error(
            "[KnowledgeWS] Unexpected error project=%s: %s",
            project_id,
            exc,
            exc_info=True,
        )
    finally:
        await _unregister(project_id, websocket)
