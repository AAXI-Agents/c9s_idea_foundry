"""WebSocket endpoint — real-time agent activity for flow runs.

Provides ``WS /flow/runs/{run_id}/ws`` for bidirectional communication
during PRD generation.  Clients receive:

- **status_update** — when the run status changes (inprogress, paused, completed)
- **agent_activity** — when a new agent interaction is logged
- **progress** — pipeline stage start/complete/skip events

Clients can send:

- ``{"type": "ping"}`` — server replies ``{"type": "pong"}``
- ``{"type": "approve", "run_id": "..."}`` — (future) inline approval
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

ws_router = APIRouter()

# ── Connection hub ─────────────────────────────────────────────

# run_id → set of connected WebSockets
_connections: dict[str, set[WebSocket]] = {}
_lock = asyncio.Lock()


async def _register(run_id: str, ws: WebSocket) -> None:
    async with _lock:
        _connections.setdefault(run_id, set()).add(ws)


async def _unregister(run_id: str, ws: WebSocket) -> None:
    async with _lock:
        conns = _connections.get(run_id)
        if conns:
            conns.discard(ws)
            if not conns:
                del _connections[run_id]


async def broadcast(run_id: str, event: dict[str, Any]) -> None:
    """Send *event* to all WebSocket clients connected to *run_id*.

    Called from background flow tasks via ``get_event_loop().call_soon_threadsafe()``.
    Silently drops messages for disconnected clients.
    """
    async with _lock:
        conns = _connections.get(run_id)
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
            _connections.pop(run_id, None)


def broadcast_sync(run_id: str, event: dict[str, Any]) -> None:
    """Thread-safe broadcast — callable from synchronous background tasks.

    Acquires the running event loop and schedules the broadcast
    coroutine.  If no loop is running (e.g. during tests), the event
    is silently dropped.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(broadcast(run_id, event))
        else:
            loop.run_until_complete(broadcast(run_id, event))
    except RuntimeError:
        pass  # no event loop — skip


# ── Helpers ────────────────────────────────────────────────────


def _build_status_snapshot(run_id: str) -> dict[str, Any]:
    """Build a status snapshot from in-memory runs or MongoDB."""
    from crewai_productfeature_planner.apis.shared import runs

    run = runs.get(run_id)
    if run is not None:
        return {
            "type": "status_update",
            "run_id": run_id,
            "status": run.status.value if hasattr(run.status, "value") else str(run.status),
            "iteration": run.iteration,
            "current_section_key": run.current_section_key,
            "sections_approved": sum(1 for s in run.current_draft.sections if s.is_approved),
            "sections_total": len(run.current_draft.sections),
            "active_agents": run.active_agents,
            "error": run.error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Fallback: check MongoDB for persisted runs
    from crewai_productfeature_planner.mongodb.crew_jobs import find_job

    job = find_job(run_id)
    if job is not None:
        return {
            "type": "status_update",
            "run_id": run_id,
            "status": job.get("status", "unknown"),
            "iteration": 0,
            "current_section_key": "",
            "sections_approved": 0,
            "sections_total": 0,
            "active_agents": [],
            "error": job.get("error"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return {
        "type": "error",
        "run_id": run_id,
        "message": f"Run {run_id} not found",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _interaction_to_event(doc: dict) -> dict[str, Any]:
    """Convert an agentInteraction document to a WebSocket event."""
    created = doc.get("created_at")
    if hasattr(created, "isoformat"):
        created = created.isoformat()
    return {
        "type": "agent_activity",
        "interaction_id": doc.get("interaction_id", ""),
        "source": doc.get("source", ""),
        "intent": doc.get("intent", ""),
        "agent_response": doc.get("agent_response", ""),
        "run_id": doc.get("run_id"),
        "user_id": doc.get("user_id"),
        "created_at": str(created) if created else "",
        "predicted_next_step": doc.get("predicted_next_step"),
    }


# ── Polling loop ───────────────────────────────────────────────


async def _poll_loop(
    ws: WebSocket,
    run_id: str,
    poll_interval: float = 2.0,
) -> None:
    """Background polling task — sends status updates and new interactions.

    Runs alongside the receive loop.  Terminates when the run
    completes or the WebSocket disconnects.
    """
    from crewai_productfeature_planner.mongodb.agent_interactions import (
        find_interactions,
    )

    last_interaction_ts: datetime | None = None
    last_status: str = ""

    while True:
        try:
            # Status check
            snapshot = _build_status_snapshot(run_id)
            current_status = snapshot.get("status", "")

            if current_status != last_status:
                await ws.send_json(snapshot)
                last_status = current_status

            # New interactions since last check
            kwargs: dict[str, Any] = {"run_id": run_id, "limit": 10}
            if last_interaction_ts is not None:
                kwargs["since"] = last_interaction_ts

            docs = find_interactions(**kwargs)

            for doc in reversed(docs):  # oldest first
                event = _interaction_to_event(doc)
                await ws.send_json(event)
                doc_ts = doc.get("created_at")
                if isinstance(doc_ts, datetime):
                    last_interaction_ts = doc_ts
                elif last_interaction_ts is None:
                    last_interaction_ts = datetime.now(timezone.utc)

            # Stop polling once the run is terminal
            if current_status in ("completed", "failed", "archived"):
                await ws.send_json({
                    "type": "complete",
                    "run_id": run_id,
                    "status": current_status,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                break

            await asyncio.sleep(poll_interval)

        except (WebSocketDisconnect, RuntimeError):
            break
        except Exception:  # noqa: BLE001
            logger.debug(
                "[WS] Poll error for run_id=%s", run_id, exc_info=True,
            )
            await asyncio.sleep(poll_interval)


# ── WebSocket endpoint ─────────────────────────────────────────

# Set to False in tests to disable the background poll loop.
_enable_poll_loop: bool = True


@ws_router.websocket("/flow/runs/{run_id}/ws")
async def flow_run_websocket(websocket: WebSocket, run_id: str):
    """Bidirectional WebSocket for real-time flow run updates.

    On connect, sends the current run status snapshot immediately,
    then polls for status changes and new agent interactions.
    The client can send JSON messages (e.g. ``{"type": "ping"}``).
    """
    await websocket.accept()
    logger.info("[WS] Client connected for run_id=%s", run_id)

    await _register(run_id, websocket)

    # Send initial status snapshot
    snapshot = _build_status_snapshot(run_id)
    try:
        await websocket.send_json(snapshot)
    except Exception:  # noqa: BLE001
        await _unregister(run_id, websocket)
        return

    # Start background poll task (disabled in tests)
    poll_task = None
    if _enable_poll_loop:
        poll_task = asyncio.create_task(_poll_loop(websocket, run_id))

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON",
                })
                continue

            msg_type = msg.get("type", "")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg_type == "get_status":
                snap = _build_status_snapshot(run_id)
                await websocket.send_json(snap)
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                })

    except WebSocketDisconnect:
        logger.info("[WS] Client disconnected for run_id=%s", run_id)
    except Exception:  # noqa: BLE001
        logger.debug("[WS] Connection error for run_id=%s", run_id, exc_info=True)
    finally:
        if poll_task is not None:
            poll_task.cancel()
        await _unregister(run_id, websocket)
