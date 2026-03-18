"""Decision resolution — bridge between Slack button clicks and flow waits."""

from __future__ import annotations

from crewai_productfeature_planner.apis.slack.interactive_handlers._run_state import (
    _interactive_runs,
    _lock,
    _manual_refinement_text,
    get_interactive_run,
)

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)


def resolve_interaction(run_id: str, action_id: str, user: str) -> bool:
    """Record a user's interactive decision and unblock the waiting flow.

    Args:
        run_id: The flow run identifier (from button ``value``).
        action_id: The Slack ``action_id`` (e.g. ``refinement_agent``).
        user: The Slack user ID who clicked.

    Returns:
        ``True`` if the decision was recorded, ``False`` if no pending
        action was found for this run_id.
    """
    with _lock:
        info = _interactive_runs.get(run_id)
        if not info:
            logger.warning("No interactive run found for run_id=%s", run_id)
            return False

        info["decision"] = action_id
        info["decision_user"] = user

        # Detect cancellation
        if action_id in ("flow_cancel", "idea_cancel", "requirements_cancel"):
            info["cancelled"] = True

        pending = info.get("pending_action", "unknown")
        channel = info.get("channel")
        thread_ts = info.get("thread_ts")

        logger.info(
            "Interaction resolved: run_id=%s action=%s user=%s",
            run_id, action_id, user,
        )

    # Signal outside the lock to avoid deadlock
    info["event"].set()

    # ── Track this interaction for fine-tuning data ──
    try:
        from crewai_productfeature_planner.mongodb.agent_interactions.repository import (
            log_interaction,
        )
        log_interaction(
            source="slack_interactive",
            user_message=action_id,
            intent=pending,
            agent_response=f"User chose: {action_id}",
            run_id=run_id,
            channel=channel,
            thread_ts=thread_ts,
            user_id=user,
            metadata={"action_id": action_id, "pending_action": pending},
        )
    except Exception:  # noqa: BLE001
        logger.debug("Failed to log interactive interaction", exc_info=True)

    return True


def submit_manual_refinement(run_id: str, text: str) -> bool:
    """Store a manual refinement reply from a Slack thread.

    Called by the events router when it detects a thread message for an
    active manual-refinement session.

    Returns:
        ``True`` if stored, ``False`` if no interactive run found.
    """
    with _lock:
        info = _interactive_runs.get(run_id)
        if not info:
            return False
        _manual_refinement_text[run_id] = text
        channel = info.get("channel")
        thread_ts = info.get("thread_ts")
        user = info.get("user")
    # Signal the waiting thread so it picks up the new text
    info["event"].set()

    # ── Track this interaction for fine-tuning data ──
    try:
        from crewai_productfeature_planner.mongodb.agent_interactions.repository import (
            log_interaction,
        )
        log_interaction(
            source="slack_interactive",
            user_message=text,
            intent="manual_refinement",
            agent_response="(manual refinement text submitted)",
            run_id=run_id,
            channel=channel,
            thread_ts=thread_ts,
            user_id=user,
            metadata={"action": "manual_refinement_reply"},
        )
    except Exception:  # noqa: BLE001
        logger.debug("Failed to log manual refinement interaction", exc_info=True)

    return True


def is_manual_refinement_active(run_id: str) -> bool:
    """Check if a manual refinement session is active for a run."""
    with _lock:
        info = _interactive_runs.get(run_id)
        if not info:
            return False
        return info.get("pending_action") == "manual_refinement"
