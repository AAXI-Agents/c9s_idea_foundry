"""Interactive run state management — lock, registry, TTL expiry."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Interactive run state
# ---------------------------------------------------------------------------

_lock = threading.Lock()

# run_id -> pending action info
_interactive_runs: dict[str, dict[str, Any]] = {}

# run_id -> latest manual refinement text (set by thread messages)
_manual_refinement_text: dict[str, str] = {}

# TTL for stale entries (30 minutes)
_INTERACTIVE_TTL_SECONDS = 1800


def _expire_stale() -> None:
    """Remove entries older than the TTL.  Must be called under ``_lock``."""
    now = time.time()
    expired = [
        rid for rid, info in _interactive_runs.items()
        if now - info.get("created_at", now) > _INTERACTIVE_TTL_SECONDS
    ]
    for rid in expired:
        _interactive_runs.pop(rid, None)
        _manual_refinement_text.pop(rid, None)


def register_interactive_run(
    run_id: str,
    channel: str,
    thread_ts: str,
    user: str,
    idea: str,
) -> None:
    """Register a new interactive flow run for state tracking."""
    with _lock:
        _expire_stale()
        _interactive_runs[run_id] = {
            "channel": channel,
            "thread_ts": thread_ts,
            "user": user,
            "idea": idea,
            "created_at": time.time(),
            "pending_action": None,     # str: current action type being waited on
            "event": threading.Event(),  # signalled when user makes a decision
            "decision": None,           # str: the user's choice
            "cancelled": False,
        }


def get_interactive_run(run_id: str) -> dict[str, Any] | None:
    """Return the interactive run info, or None if not found."""
    with _lock:
        return _interactive_runs.get(run_id)


def cleanup_interactive_run(run_id: str) -> None:
    """Remove a completed/cancelled interactive run."""
    with _lock:
        _interactive_runs.pop(run_id, None)
        _manual_refinement_text.pop(run_id, None)
