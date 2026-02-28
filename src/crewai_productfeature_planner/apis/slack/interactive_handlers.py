"""Slack interactive flow handlers — state management and Slack-aware callbacks.

Provides the bridge between Slack interactive components (buttons, thread
replies) and the PRD flow's callback mechanisms.  Each interactive flow
run is tracked in ``_interactive_runs`` with a ``threading.Event`` that
the flow blocks on until the user makes a decision via Slack.

Key patterns:

* **Refinement mode** — ``_wait_for_refinement_mode()`` posts Block Kit
  buttons and blocks until the user clicks one.
* **Idea approval** — ``make_slack_idea_callback()`` returns a callback
  compatible with ``PRDFlow.idea_approval_callback`` that posts the
  refined idea to Slack and waits for approve/cancel.
* **Requirements approval** — ``make_slack_requirements_callback()``
  returns a callback for ``PRDFlow.requirements_approval_callback``.
* **Manual refinement** — ``start_manual_refinement()`` enters a
  thread-based loop where the user's replies update the idea.

The ``resolve_interaction()`` function is called by the interactions
router when a button click arrives — it records the decision and
signals the waiting thread.
"""

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


# ---------------------------------------------------------------------------
# Decision resolution (called by interactions_router)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Slack message helpers
# ---------------------------------------------------------------------------


def _post_blocks(channel: str, thread_ts: str, blocks: list[dict], text: str = "") -> None:
    """Post a Block Kit message to Slack."""
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if not client:
        logger.warning("Cannot post blocks — no Slack client available")
        return
    try:
        client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            blocks=blocks,
            text=text or "PRD Flow update",
        )
    except Exception as exc:
        logger.error("Failed to post blocks to %s: %s", channel, exc)


def _post_text(channel: str, thread_ts: str, text: str) -> None:
    """Post a plain text message to Slack."""
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if not client:
        return
    try:
        client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=text)
    except Exception as exc:
        logger.error("Failed to post text to %s: %s", channel, exc)


# ---------------------------------------------------------------------------
# Wait helpers — block until user interacts
# ---------------------------------------------------------------------------


def _wait_for_decision(
    run_id: str,
    action_type: str,
    timeout: float = 600.0,
) -> str | None:
    """Block until the user makes a decision or timeout expires.

    Args:
        run_id: The flow run identifier.
        action_type: Label for the pending action (for logging).
        timeout: Max seconds to wait.

    Returns:
        The ``action_id`` string chosen by the user, or ``None`` on
        timeout.
    """
    info = get_interactive_run(run_id)
    if not info:
        return None

    with _lock:
        info["pending_action"] = action_type
        info["decision"] = None
        info["event"].clear()

    logger.info(
        "Waiting for Slack interaction: run_id=%s action=%s",
        run_id, action_type,
    )

    signalled = info["event"].wait(timeout=timeout)
    if not signalled:
        logger.warning("Timeout waiting for interaction: run_id=%s", run_id)
        return None

    return info.get("decision")


def wait_for_refinement_mode(run_id: str) -> str | None:
    """Post refinement mode blocks and wait for the user's choice.

    Returns:
        ``"agent"``, ``"manual"``, ``"cancel"``, or ``None`` on timeout.
    """
    from crewai_productfeature_planner.apis.slack.blocks import refinement_mode_blocks

    info = get_interactive_run(run_id)
    if not info:
        return None

    blocks = refinement_mode_blocks(run_id, info["idea"])
    _post_blocks(info["channel"], info["thread_ts"], blocks,
                 text="How would you like to refine this idea?")

    decision = _wait_for_decision(run_id, "refinement_mode")

    if decision == "refinement_agent":
        return "agent"
    elif decision == "refinement_manual":
        return "manual"
    elif decision in ("flow_cancel", "idea_cancel"):
        return "cancel"
    return None


# ---------------------------------------------------------------------------
# Manual refinement loop
# ---------------------------------------------------------------------------


def run_manual_refinement(run_id: str) -> tuple[str, list[dict]]:
    """Run an interactive manual refinement loop via Slack thread.

    Posts the idea with approve/edit buttons.  When the user replies
    in the thread, the reply becomes the new idea.  When they click
    "Approve", the loop ends.

    Returns:
        ``(refined_idea, refinement_history)``
    """
    from crewai_productfeature_planner.apis.slack.blocks import manual_refinement_prompt_blocks

    info = get_interactive_run(run_id)
    if not info:
        return info["idea"] if info else "", []

    current_idea = info["idea"]
    iteration = 0
    history: list[dict] = []

    while True:
        iteration += 1
        blocks = manual_refinement_prompt_blocks(run_id, current_idea, iteration)
        _post_blocks(
            info["channel"], info["thread_ts"], blocks,
            text=f"Idea Refinement — Iteration {iteration}",
        )

        # Wait for either a button click or a thread reply
        with _lock:
            info["pending_action"] = "manual_refinement"
            info["decision"] = None
            info["event"].clear()
            _manual_refinement_text.pop(run_id, None)

        info["event"].wait(timeout=600.0)
        decision = info.get("decision")

        # Check if user sent a thread reply (manual refinement text)
        with _lock:
            revised_text = _manual_refinement_text.pop(run_id, None)

        if decision in ("idea_approve",):
            logger.info(
                "Manual refinement approved after %d iteration(s) for run_id=%s",
                iteration, run_id,
            )
            return current_idea, history

        if decision in ("idea_cancel", "flow_cancel"):
            info["cancelled"] = True
            return current_idea, history

        if revised_text:
            current_idea = revised_text
            history.append({"iteration": iteration, "idea": current_idea})
            logger.info(
                "Manual refinement iteration %d for run_id=%s (%d chars)",
                iteration, run_id, len(current_idea),
            )
            continue

        # Timeout or unknown — treat as cancel
        logger.warning("Manual refinement timeout/unknown for run_id=%s", run_id)
        return current_idea, history


# ---------------------------------------------------------------------------
# PRDFlow callback factories
# ---------------------------------------------------------------------------


def make_slack_idea_callback(run_id: str):
    """Create an ``idea_approval_callback`` that prompts via Slack.

    Returns a callable with the same signature as
    ``main._approve_refined_idea``.
    """
    from crewai_productfeature_planner.apis.slack.blocks import idea_approval_blocks

    def _callback(
        refined_idea: str,
        original_idea: str,
        cb_run_id: str,
        refinement_history: list[dict] | None = None,
    ) -> bool:
        info = get_interactive_run(run_id)
        if not info:
            return False  # continue (auto-approve if no interactive run)

        blocks = idea_approval_blocks(run_id, refined_idea, original_idea)
        _post_blocks(
            info["channel"], info["thread_ts"], blocks,
            text="Idea Refinement Complete — approve or cancel?",
        )

        decision = _wait_for_decision(run_id, "idea_approval")

        if decision == "idea_approve":
            logger.info("Slack idea approved for run_id=%s", run_id)
            return False  # continue to section drafting

        if decision in ("idea_cancel", "flow_cancel"):
            logger.info("Slack idea cancelled for run_id=%s", run_id)
            info["cancelled"] = True
            # Raise IdeaFinalized to stop the flow gracefully
            from crewai_productfeature_planner.flows.prd_flow import IdeaFinalized
            raise IdeaFinalized(f"Cancelled via Slack by user")

        # Timeout — auto-approve to avoid blocking forever
        logger.warning("Idea approval timeout for run_id=%s — auto-approving", run_id)
        return False

    return _callback


def make_slack_requirements_callback(run_id: str):
    """Create a ``requirements_approval_callback`` that prompts via Slack.

    Returns a callable with the same signature as
    ``main._approve_requirements``.
    """
    from crewai_productfeature_planner.apis.slack.blocks import requirements_approval_blocks

    def _callback(
        requirements: str,
        idea: str,
        cb_run_id: str,
        breakdown_history: list[dict] | None = None,
    ) -> bool:
        info = get_interactive_run(run_id)
        if not info:
            return False  # auto-approve

        iteration_count = len(breakdown_history) if breakdown_history else 0
        blocks = requirements_approval_blocks(run_id, requirements, iteration_count)
        _post_blocks(
            info["channel"], info["thread_ts"], blocks,
            text="Requirements Breakdown Complete — approve or cancel?",
        )

        decision = _wait_for_decision(run_id, "requirements_approval")

        if decision == "requirements_approve":
            logger.info("Slack requirements approved for run_id=%s", run_id)
            return False  # continue to PRD section drafting

        if decision in ("requirements_cancel", "flow_cancel"):
            logger.info("Slack requirements cancelled for run_id=%s", run_id)
            info["cancelled"] = True
            from crewai_productfeature_planner.flows.prd_flow import RequirementsFinalized
            raise RequirementsFinalized(f"Cancelled via Slack by user")

        # Timeout — auto-approve
        logger.warning(
            "Requirements approval timeout for run_id=%s — auto-approving",
            run_id,
        )
        return False

    return _callback


# ---------------------------------------------------------------------------
# Full interactive flow runner
# ---------------------------------------------------------------------------


def run_interactive_slack_flow(
    run_id: str,
    idea: str,
    channel: str,
    thread_ts: str,
    user: str,
    notify: bool = True,
    webhook_url: str | None = None,
    project_id: str | None = None,
) -> None:
    """Execute the PRD flow with full Slack interactive support.

    Mirrors the CLI ``_run_single_flow()`` experience:
    1. Ask refinement mode (agent vs manual) via buttons
    2. If manual: run thread-based refinement loop
    3. Approve refined idea via buttons
    4. Approve requirements via buttons
    5. Auto-generate sections (like CLI after requirements approve)
    6. Post results to Slack

    If *project_id* is provided, the working-idea document will be
    linked to the project via ``save_project_ref`` once the flow
    finishes so that publishing can resolve project-level keys.

    This runs in a background thread and communicates with the user
    exclusively through Slack interactive messages.
    """
    from crewai_productfeature_planner.apis.prd.service import run_prd_flow
    from crewai_productfeature_planner.apis.shared import FlowRun, FlowStatus, runs
    from crewai_productfeature_planner.apis.slack.blocks import (
        flow_cancelled_blocks,
        flow_started_blocks,
    )
    from crewai_productfeature_planner.apis.slack.router import _deliver_webhook
    from crewai_productfeature_planner.mongodb.crew_jobs import create_job
    from crewai_productfeature_planner.tools.slack_tools import (
        SlackPostPRDResultTool,
        SlackSendMessageTool,
    )

    send_tool = SlackSendMessageTool()

    # Register interactive state
    register_interactive_run(run_id, channel, thread_ts, user, idea)

    # Create the FlowRun record and crew job
    runs[run_id] = FlowRun(run_id=run_id, flow_name="prd")
    create_job(run_id, idea)

    try:
        # Step 1: Ask refinement mode
        mode = wait_for_refinement_mode(run_id)

        info = get_interactive_run(run_id)
        if not info or info.get("cancelled") or mode == "cancel":
            blocks = flow_cancelled_blocks(run_id, "refinement mode selection")
            _post_blocks(channel, thread_ts, blocks, text="PRD flow cancelled")
            runs[run_id].status = FlowStatus.FAILED
            runs[run_id].error = "Cancelled by user at refinement mode"
            return

        if mode is None:
            # Timeout — default to agent mode
            _post_text(
                channel, thread_ts,
                ":hourglass: No response received — defaulting to agent refinement.",
            )
            mode = "agent"

        # Step 2: Manual refinement (if chosen)
        if mode == "manual":
            refined_idea, history = run_manual_refinement(run_id)
            info = get_interactive_run(run_id)
            if info and info.get("cancelled"):
                blocks = flow_cancelled_blocks(run_id, "manual idea refinement")
                _post_blocks(channel, thread_ts, blocks, text="PRD flow cancelled")
                runs[run_id].status = FlowStatus.FAILED
                runs[run_id].error = "Cancelled by user during manual refinement"
                return
            idea = refined_idea
            # Update the registered idea
            with _lock:
                if run_id in _interactive_runs:
                    _interactive_runs[run_id]["idea"] = idea

        # Step 3: Start the PRD flow with Slack-aware callbacks
        if notify:
            blocks = flow_started_blocks(run_id, idea)
            _post_blocks(channel, thread_ts, blocks,
                         text=f"PRD flow started for: {idea[:80]}")

        # Run the PRD flow — use Slack callbacks for idea/requirements approval
        # The flow will call these callbacks at the appropriate points
        from crewai_productfeature_planner.flows.prd_flow import (
            IdeaFinalized,
            PauseRequested,
            PRDFlow,
            RequirementsFinalized,
        )
        from crewai_productfeature_planner.mongodb.crew_jobs import (
            update_job_completed,
            update_job_started,
        )
        from crewai_productfeature_planner.scripts.retry import BillingError, LLMError

        runs[run_id].status = FlowStatus.RUNNING
        update_job_started(run_id)

        flow = PRDFlow()
        flow.state.idea = idea
        flow.state.run_id = run_id

        # If mode was manual, the idea is already refined
        if mode == "manual":
            flow.state.idea_refined = True
            flow.state.original_idea = get_interactive_run(run_id).get("idea", idea)
        else:
            # Agent mode: set callbacks for interactive approval gates
            flow.idea_approval_callback = make_slack_idea_callback(run_id)

        flow.requirements_approval_callback = make_slack_requirements_callback(run_id)

        try:
            result = flow.kickoff()

            # Link working idea to project (doc exists after kickoff)
            if project_id:
                try:
                    from crewai_productfeature_planner.mongodb.working_ideas.repository import (
                        save_project_ref,
                    )
                    save_project_ref(run_id, project_id)
                except Exception:  # noqa: BLE001
                    logger.debug("save_project_ref failed for %s", run_id, exc_info=True)

            run = runs.get(run_id)
            if run:
                run.result = result
                run.status = FlowStatus.COMPLETED
                # Sync state
                from crewai_productfeature_planner.apis.prd.service import _sync_flow_state_to_run
                _sync_flow_state_to_run(run_id, flow)

            update_job_completed(run_id, status="completed")

            if notify:
                post_tool = SlackPostPRDResultTool()
                run = runs.get(run_id)
                post_tool.run(
                    channel=channel,
                    idea=idea,
                    output_file=run.output_file if run else "",
                    confluence_url=run.confluence_url if run else "",
                    jira_output=run.jira_output if run else "",
                    thread_ts=thread_ts,
                )
            logger.info("Interactive Slack PRD flow %s completed", run_id)

            # Proactively suggest next step after PRD completion
            try:
                from crewai_productfeature_planner.apis.slack._next_step import (
                    predict_and_post_next_step,
                )
                predict_and_post_next_step(
                    channel=channel,
                    thread_ts=thread_ts,
                    user=user,
                    trigger_action="prd_completed",
                )
            except Exception as ns_exc:
                logger.warning("Next-step after PRD completion failed: %s", ns_exc)

        except IdeaFinalized:
            update_job_completed(run_id, status="completed")
            if notify:
                blocks = flow_cancelled_blocks(run_id, "idea approval")
                _post_blocks(channel, thread_ts, blocks, text="PRD flow cancelled at idea approval")
            runs[run_id].status = FlowStatus.COMPLETED

        except RequirementsFinalized:
            update_job_completed(run_id, status="completed")
            if notify:
                blocks = flow_cancelled_blocks(run_id, "requirements approval")
                _post_blocks(channel, thread_ts, blocks,
                             text="PRD flow cancelled at requirements approval")
            runs[run_id].status = FlowStatus.COMPLETED

        except PauseRequested:
            update_job_completed(run_id, status="paused")
            runs[run_id].status = FlowStatus.PAUSED
            if notify:
                send_tool.run(
                    channel=channel,
                    text=(
                        f":pause_button: PRD flow paused (`{run_id}`). "
                        "Resume via the API."
                    ),
                    thread_ts=thread_ts,
                )

        except (BillingError, LLMError) as exc:
            update_job_completed(run_id, status="paused")
            runs[run_id].status = FlowStatus.PAUSED
            runs[run_id].error = str(exc)
            if notify:
                send_tool.run(
                    channel=channel,
                    text=f":warning: PRD flow paused due to error: {exc}",
                    thread_ts=thread_ts,
                )

    except Exception as exc:
        logger.error("Interactive Slack PRD flow %s failed: %s", run_id, exc)
        runs[run_id].status = FlowStatus.FAILED
        runs[run_id].error = str(exc)
        if notify:
            try:
                send_tool.run(
                    channel=channel,
                    text=f":x: PRD flow failed: {exc}",
                    thread_ts=thread_ts,
                )
            except Exception:
                pass

    finally:
        if webhook_url:
            run = runs.get(run_id)
            _deliver_webhook(
                run_id,
                result=run.result if run else None,
                error=run.error if run else None,
                webhook_url=webhook_url,
            )
        cleanup_interactive_run(run_id)
