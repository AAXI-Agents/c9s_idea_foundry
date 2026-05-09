"""Token streaming support for ideation agent — broadcasts LLM chunks via WS.

Uses the CrewAI event bus ``LLMStreamChunkEvent`` to intercept streaming
tokens during ideation agent execution.  A thread-local context ties each
executor thread to the active ideation session so the global event handler
only broadcasts for ideation calls (not PRD flow or other agents).

Usage in ``service.py``::

    from crewai_productfeature_planner.apis.ideation._streaming import (
        streaming_session,
    )

    def _run_in_thread():
        with streaming_session(session_id, step):
            return run_ideation_step(...)
"""

from __future__ import annotations

import threading
import uuid
from contextlib import contextmanager
from typing import Generator

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# ── Thread-local context ────────────────────────────────────────
# Each ideation executor thread sets session_id + step before the
# crew.kickoff() call.  The event handler checks this to decide
# whether to broadcast.

_ctx = threading.local()


@contextmanager
def streaming_session(
    session_id: str,
    step: str,
) -> Generator[None, None, None]:
    """Context manager — sets thread-local session for token streaming.

    Must be entered **inside** the executor thread (i.e. inside the
    callable passed to ``run_in_executor``).
    """
    token = uuid.uuid4().hex[:12]
    _ctx.session_id = session_id
    _ctx.step = step
    _ctx.message_token = token
    logger.debug(
        "[IdeationStreaming] Streaming context opened session=%s step=%s",
        session_id,
        step,
    )
    try:
        yield
    finally:
        _ctx.session_id = None
        _ctx.step = None
        _ctx.message_token = None
        logger.debug(
            "[IdeationStreaming] Streaming context closed session=%s step=%s",
            session_id,
            step,
        )


def _broadcast_agent_token(session_id: str, step: str, chunk: str) -> None:
    """Emit an ``agent_token`` WebSocket event for a single LLM chunk."""
    try:
        from crewai_productfeature_planner.apis.ideation._route_websocket import (
            broadcast_sync,
        )
        from crewai_productfeature_planner.mongodb.ideation_sessions.repository import (
            step_to_name,
        )

        broadcast_sync(session_id, {
            "event": "agent_token",
            "data": {
                "message_id": f"streaming-{session_id[:8]}",
                "token": chunk,
                "is_final": False,
                "step": step_to_name(step),
            },
        })
    except Exception as exc:
        logger.debug(
            "[IdeationStreaming] Failed to broadcast token session=%s: %s",
            session_id,
            exc,
        )


# ── CrewAI event bus handler ───────────────────────────────────
# Registered once at import time.  Fires for *every* LLM streaming
# chunk system-wide, but the thread-local check ensures we only
# broadcast for ideation sessions.

def _on_stream_chunk(source: object, event: object) -> None:
    """Handle ``LLMStreamChunkEvent`` — forward to WS if in ideation context."""
    session_id = getattr(_ctx, "session_id", None)
    if not session_id:
        return  # Not an ideation thread — ignore

    chunk = getattr(event, "chunk", None)
    if not chunk:
        return

    step = getattr(_ctx, "step", None) or "a"
    _broadcast_agent_token(session_id, step, chunk)


def _register_handler() -> None:
    """Register the streaming chunk handler on the CrewAI event bus."""
    try:
        from crewai.events.event_bus import crewai_event_bus
        from crewai.events.types.llm_events import LLMStreamChunkEvent

        crewai_event_bus.register_handler(LLMStreamChunkEvent, _on_stream_chunk)
        logger.info("[IdeationStreaming] Registered LLMStreamChunkEvent handler")
    except ImportError:
        logger.warning(
            "[IdeationStreaming] Could not import crewai event bus — "
            "token streaming disabled"
        )
    except Exception as exc:
        logger.warning(
            "[IdeationStreaming] Failed to register handler: %s", exc
        )


# Auto-register on module import
_register_handler()
