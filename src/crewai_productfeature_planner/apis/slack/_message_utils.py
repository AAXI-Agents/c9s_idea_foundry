"""Small utilities for the message handler — idea extraction and logging."""

from __future__ import annotations

import re as _re

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Idea number extraction
# ---------------------------------------------------------------------------

_IDEA_NUM_RE = _re.compile(
    r"(?:idea\s*#?\s*(\d+)|#\s*(\d+))",
    _re.IGNORECASE,
)


def extract_idea_number(text: str) -> int | None:
    """Extract 1-based idea number from text like 'idea #1', 'idea 2', '#3'.

    Returns the integer or ``None`` if no number reference is found.
    """
    m = _IDEA_NUM_RE.search(text)
    if m:
        num_str = m.group(1) or m.group(2)
        try:
            return int(num_str)
        except (ValueError, TypeError):
            return None
    return None


# ---------------------------------------------------------------------------
# Interaction logging helper
# ---------------------------------------------------------------------------


def log_tracked_interaction(
    log_fn,
    source: str,
    user_message: str,
    intent: str,
    agent_response: str,
    idea: str | None,
    run_id: str | None,
    project_id: str | None,
    channel: str,
    thread_ts: str,
    user_id: str,
    history: list | None = None,
    metadata: dict | None = None,
    predicted_next_step: dict | None = None,
) -> str | None:
    """Wrapper to log an agent interaction, swallowing errors.

    Returns the ``interaction_id`` on success, or ``None``.
    """
    try:
        return log_fn(
            source=source,
            user_message=user_message,
            intent=intent,
            agent_response=agent_response,
            idea=idea,
            run_id=run_id,
            project_id=project_id,
            channel=channel,
            thread_ts=thread_ts,
            user_id=user_id,
            conversation_history=history or None,
            metadata=metadata,
            predicted_next_step=predicted_next_step,
        )
    except Exception:  # noqa: BLE001
        logger.debug("Failed to log agent interaction", exc_info=True)
        return None
