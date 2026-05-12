"""WebSocket endpoint — real-time agent streaming for ideation sessions.

Provides ``WS /ws/ideation/{session_id}`` for bidirectional communication
during the ideation flow. Clients receive:

- **agent_typing** — agent is generating a response (typing indicator)
- **agent_message** — complete agent message
- **step_advanced** — session moved to next step
- **session_completed** — all steps done, PRD triggered
- **error** — an error occurred

Clients can send:

- ``{"type": "ping"}`` — server replies ``{"type": "pong"}``
- ``{"type": "respond", "content": "..."}`` — user response
- ``{"type": "advance"}`` — approve and advance
- ``{"type": "rollback"}`` — go back one step
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from crewai_productfeature_planner.mongodb._tenant import TenantContext
from crewai_productfeature_planner.mongodb.ideation_sessions.repository import (
    get_session,
    step_to_name,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

ws_router = APIRouter()

# session_id → set of connected WebSockets
_connections: dict[str, set[WebSocket]] = {}
_lock = asyncio.Lock()

# Stash the main event loop so worker threads (ThreadPoolExecutor) can
# schedule coroutines on it via ``asyncio.run_coroutine_threadsafe``.
_main_loop: asyncio.AbstractEventLoop | None = None


def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Called once during app startup to capture the main event loop."""
    global _main_loop  # noqa: PLW0603
    _main_loop = loop


async def _register(session_id: str, ws: WebSocket) -> None:
    async with _lock:
        _connections.setdefault(session_id, set()).add(ws)


async def _unregister(session_id: str, ws: WebSocket) -> None:
    async with _lock:
        conns = _connections.get(session_id)
        if conns:
            conns.discard(ws)
            if not conns:
                del _connections[session_id]


async def broadcast(session_id: str, event: dict[str, Any]) -> None:
    """Send *event* to all WebSocket clients connected to *session_id*."""
    async with _lock:
        conns = _connections.get(session_id)
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
            _connections.pop(session_id, None)


def broadcast_sync(session_id: str, event: dict[str, Any]) -> None:
    """Thread-safe broadcast — callable from synchronous CrewAI agent tasks.

    Works correctly from both the main async thread (where the event loop
    is already running) and from ``ThreadPoolExecutor`` worker threads
    (where no event loop exists).  In the latter case we use
    ``asyncio.run_coroutine_threadsafe`` to schedule the coroutine on the
    main loop, which is stashed in ``_main_loop`` at import time.
    """
    try:
        loop = asyncio.get_running_loop()
        # We're inside an async context — schedule directly.
        future = asyncio.ensure_future(broadcast(session_id, event), loop=loop)
        future.add_done_callback(_log_broadcast_error)
        return
    except RuntimeError:
        pass  # No running loop in this thread — fall through

    # We're in a worker thread (ThreadPoolExecutor).  Use the stashed
    # main event loop to schedule the broadcast.
    loop = _main_loop
    if loop is not None and loop.is_running():
        asyncio.run_coroutine_threadsafe(broadcast(session_id, event), loop)
    else:
        logger.warning(
            "[IdeationWS] broadcast_sync: no usable event loop session=%s",
            session_id,
        )


def _log_broadcast_error(future: asyncio.Future) -> None:
    """Callback for broadcast futures — log any exception."""
    exc = future.exception()
    if exc:
        logger.warning("[IdeationWS] broadcast future failed: %s", exc)


def _build_session_snapshot(
    session_id: str,
    tenant: TenantContext | None = None,
) -> dict[str, Any]:
    """Build a status snapshot from the session document."""
    session = get_session(session_id=session_id, tenant=tenant)
    if not session:
        return {
            "type": "error",
            "session_id": session_id,
            "message": f"Session {session_id} not found",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return {
        "type": "session_state",
        "session_id": session_id,
        "status": session["status"],
        "current_step": step_to_name(session["current_step"]),
        "steps_data": session.get("steps_data", {}),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def _validate_ws_token(token: str | None) -> dict[str, Any] | None:
    """Validate a JWT token for WebSocket auth.

    Returns user claims dict on success, None on failure.
    Mirrors the same validation logic as ``require_sso_user`` including
    the public-key refresh fallback.
    """
    import os

    # If SSO is disabled, allow all connections (dev mode)
    if os.environ.get("SSO_ENABLED", "false").strip().lower() not in ("true", "1", "yes"):
        return {
            "user_id": "anonymous",
            "roles": ["SYS_ADMIN"],
            "enterprise_id": os.environ.get("DEV_ENTERPRISE_ID", "dev-enterprise"),
            "organization_id": os.environ.get("DEV_ORGANIZATION_ID", "dev-org"),
        }

    if not token:
        return None

    # Use the same decode logic as the REST auth
    from crewai_productfeature_planner.apis.sso_auth import (
        _decode_jwt_locally,
        _fetch_and_save_public_key,
        _introspect_remotely,
    )

    # Try remote introspection first, then local decode
    claims = await _introspect_remotely(token)
    if claims is None:
        claims = _decode_jwt_locally(token)

    # Fallback: refresh the public key and retry local decode
    # (matches require_sso_user behaviour for key rotation recovery)
    if claims is None:
        new_key = await _fetch_and_save_public_key()
        if new_key:
            claims = _decode_jwt_locally(token)

    return claims


@ws_router.websocket("/ws/ideation/{session_id}")
async def ideation_websocket(
    websocket: WebSocket,
    session_id: str,
    token: str | None = Query(default=None),
):
    """WebSocket endpoint for real-time ideation session updates.

    Authenticates via ?token= query param (JWT access token).
    Accepts the connection first so the client receives structured
    error messages (e.g. token_expired) it can act on.
    """
    await websocket.accept()

    # Validate token after accepting so the client gets a structured
    # error message it can use to decide whether to refresh & retry.
    user = await _validate_ws_token(token)
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
            "[IdeationWS] Rejected — %s session=%s",
            error_code.lower(),
            session_id,
        )
        return

    # Resolve tenant context from JWT claims (same as REST endpoints).
    tenant = TenantContext.from_user(user)

    # Verify session exists AND is visible to this tenant. Passing
    # tenant=tenant means cross-tenant session_ids return None and the
    # WebSocket is closed before any data is sent.
    session = get_session(session_id=session_id, tenant=tenant)
    if not session:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Session {session_id} not found",
        }))
        await websocket.close(code=4004)
        return

    await _register(session_id, websocket)
    logger.info("[IdeationWS] Client connected session=%s", session_id)

    # Send initial state snapshot
    snapshot = _build_session_snapshot(session_id, tenant=tenant)
    await websocket.send_text(json.dumps(snapshot, default=str))

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON",
                }))
                continue

            msg_type = msg.get("event") or msg.get("type", "")

            if msg_type == "ping":
                await websocket.send_text(json.dumps({"event": "pong"}))

            elif msg_type == "get_status":
                snapshot = _build_session_snapshot(session_id, tenant=tenant)
                await websocket.send_text(json.dumps(snapshot, default=str))

            elif msg_type == "respond":
                content = msg.get("content", "").strip()
                if not content:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Empty content",
                    }))
                    continue

                # Send typing indicator
                # NOTE: The service layer broadcasts agent_typing +
                # processing_status events internally, so we skip the
                # duplicate broadcast here to avoid double-fire.

                # Process via service (imported lazily to avoid circular)
                from crewai_productfeature_planner.apis.ideation.service import (
                    handle_user_response,
                )

                try:
                    result = await handle_user_response(
                        session_id=session_id,
                        content=content,
                        tenant=tenant,
                    )
                except Exception as exc:
                    logger.error(
                        "[IdeationWS] handle_user_response crashed session=%s: %s",
                        session_id, exc, exc_info=True,
                    )
                    await websocket.send_text(json.dumps({
                        "event": "error",
                        "data": {
                            "code": "AGENT_ERROR",
                            "message": "Failed to process your message. Please try again.",
                            "recoverable": True,
                        },
                    }))
                    continue

                if result:
                    # Service already broadcasts the agent message via
                    # _broadcast_message() — no duplicate broadcast needed.
                    pass
                else:
                    # handle_user_response returned None — session not found or inactive
                    logger.warning(
                        "[IdeationWS] handle_user_response returned None session=%s",
                        session_id,
                    )
                    # Re-fetch session to give specific error
                    fresh_session = get_session(session_id=session_id, tenant=tenant)
                    if not fresh_session:
                        error_msg = "Session not found. It may have been deleted."
                        error_code = "SESSION_NOT_FOUND"
                    elif fresh_session["status"] != "active":
                        error_msg = f"Session is {fresh_session['status']} and cannot accept responses."
                        error_code = "SESSION_INACTIVE"
                    else:
                        error_msg = "Unable to process your message. Please try again."
                        error_code = "PROCESSING_FAILED"
                    await websocket.send_text(json.dumps({
                        "event": "error",
                        "data": {
                            "code": error_code,
                            "message": error_msg,
                            "recoverable": error_code != "SESSION_NOT_FOUND",
                        },
                    }))

            elif msg_type == "advance":
                from crewai_productfeature_planner.apis.ideation.service import (
                    handle_advance,
                )

                try:
                    result = await handle_advance(session_id=session_id, tenant=tenant)
                except Exception as exc:
                    logger.error(
                        "[IdeationWS] handle_advance crashed session=%s: %s",
                        session_id, exc, exc_info=True,
                    )
                    await websocket.send_text(json.dumps({
                        "event": "error",
                        "data": {
                            "code": "ADVANCE_ERROR",
                            "message": "Failed to advance step. Please try again.",
                            "recoverable": True,
                        },
                    }))
                    continue

                if result.get("error"):
                    await websocket.send_text(json.dumps({
                        "event": "error",
                        "data": {
                            "code": "ADVANCE_FAILED",
                            "message": result["error"],
                            "recoverable": True,
                        },
                    }))
                elif result.get("completed"):
                    await broadcast(session_id, {
                        "event": "session_completed",
                        "data": {
                            "session_id": session_id,
                            "prd_run_id": result.get("prd_run_id"),
                        },
                    })
                elif "new_step" in result:
                    await broadcast(session_id, {
                        "event": "step_advanced",
                        "data": {
                            "previous_step": step_to_name(result["previous_step"]),
                            "current_step": step_to_name(result["new_step"]),
                        },
                    })

            elif msg_type == "rollback":
                from crewai_productfeature_planner.apis.ideation.service import (
                    handle_rollback,
                )

                try:
                    result = await handle_rollback(session_id=session_id, tenant=tenant)
                except Exception as exc:
                    logger.error(
                        "[IdeationWS] handle_rollback crashed session=%s: %s",
                        session_id, exc, exc_info=True,
                    )
                    await websocket.send_text(json.dumps({
                        "event": "error",
                        "data": {
                            "code": "ROLLBACK_ERROR",
                            "message": "Failed to roll back. Please try again.",
                            "recoverable": True,
                        },
                    }))
                    continue

                if "error" not in result:
                    await broadcast(session_id, {
                        "event": "step_advanced",
                        "data": {
                            "previous_step": step_to_name(result["previous_step"]),
                            "current_step": step_to_name(result["new_step"]),
                        },
                    })
                else:
                    await websocket.send_text(json.dumps({
                        "event": "error",
                        "data": {
                            "code": "ROLLBACK_FAILED",
                            "message": result["error"],
                            "recoverable": True,
                        },
                    }))

            else:
                await websocket.send_text(json.dumps({
                    "event": "error",
                    "data": {
                        "code": "UNKNOWN_MESSAGE_TYPE",
                        "message": f"Unknown message type: {msg_type}",
                        "recoverable": True,
                    },
                }))

    except WebSocketDisconnect:
        logger.info("[IdeationWS] Client disconnected session=%s", session_id)
    except Exception as exc:
        logger.error(
            "[IdeationWS] Error session=%s: %s",
            session_id,
            exc,
            exc_info=True,
        )
        # Attempt to send error event before connection drops
        try:
            await websocket.send_text(json.dumps({
                "event": "error",
                "data": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred. Please reconnect.",
                    "recoverable": True,
                },
            }))
        except Exception:  # noqa: BLE001
            pass  # Connection already broken
    finally:
        await _unregister(session_id, websocket)
