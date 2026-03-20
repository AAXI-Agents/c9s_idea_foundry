"""Interactive run state management — lock, registry, TTL expiry."""

from __future__ import annotations

import threading
import time
from typing import Any

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Interactive run state
# ---------------------------------------------------------------------------

_lock = threading.Lock()

# run_id -> pending action info
_interactive_runs: dict[str, dict[str, Any]] = {}

# run_id -> latest manual refinement text (set by thread messages)
_manual_refinement_text: dict[str, str] = {}

# run_id -> list of feedback strings queued while the flow is running
# (not at an explicit approval gate).  The section loop drains this.
_queued_feedback: dict[str, list[str]] = {}

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
        _queued_feedback.pop(rid, None)


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
        _queued_feedback.pop(run_id, None)


def queue_feedback(run_id: str, text: str) -> bool:
    """Append user feedback for an in-progress flow (not at a gate).

    Returns ``True`` if the feedback was queued.
    """
    with _lock:
        if run_id not in _interactive_runs:
            return False
        _queued_feedback.setdefault(run_id, []).append(text)
    logger.info(
        "[QueuedFeedback] Stored feedback for run_id=%s (%d chars)",
        run_id, len(text),
    )
    return True


def drain_queued_feedback(run_id: str) -> str | None:
    """Pop and return all queued feedback joined as one string, or None."""
    with _lock:
        items = _queued_feedback.pop(run_id, [])
    if not items:
        return None
    return "\n\n".join(items)
