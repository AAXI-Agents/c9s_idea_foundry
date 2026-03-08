"""PRD flow kickoff and publishing handlers for Slack.

Extracted from ``events_router.py`` to keep the router slim.
Handles:
* PRD flow kickoff (interactive and auto-approve modes)
* Publishing to Confluence + Jira
* Publishing status checks
* Live progress / heartbeat updates during PRD generation
"""

from __future__ import annotations

import logging
import threading
import uuid
from typing import Callable

from crewai_productfeature_planner.apis.slack._thread_state import append_to_thread

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Idea-number resolution helper
# ---------------------------------------------------------------------------


def _resolve_idea_by_number(
    idea_number: int,
    project_id: str,
    channel: str,
    thread_ts: str,
    user: str,
    send_tool,
) -> dict | None:
    """Resolve a 1-based idea number to a run-info dict.

    Uses ``find_ideas_by_project`` which returns ideas in the same
    newest-first order as ``handle_list_ideas``, so numbering is
    consistent with what the user sees.

    Returns the matching idea dict (with at least ``run_id``, ``idea``,
    ``status``, ``sections_done``, ``total_sections``) or ``None``
    if the number is out of range — in which case an error message is
    posted to the Slack thread.
    """
    from crewai_productfeature_planner.mongodb.working_ideas.repository import (
        find_ideas_by_project,
    )

    ideas = find_ideas_by_project(project_id, channel=channel)

    if not ideas:
        send_tool.run(
            channel=channel,
            text=(
                f"<@{user}> :no_entry_sign: No ideas found for this project. "
                "Start a new one by telling me your idea!"
            ),
            thread_ts=thread_ts,
        )
        append_to_thread(channel, thread_ts, "assistant", "(no ideas found)")
        return None

    if idea_number < 1 or idea_number > len(ideas):
        send_tool.run(
            channel=channel,
            text=(
                f"<@{user}> :warning: Idea #{idea_number} is out of range. "
                f"There are *{len(ideas)}* idea(s) available. "
                "Say *list ideas* to see them."
            ),
            thread_ts=thread_ts,
        )
        append_to_thread(channel, thread_ts, "assistant",
                         f"(idea #{idea_number} out of range)")
        return None

    selected = ideas[idea_number - 1]
    logger.info(
        "Resolved idea #%d → run_id=%s idea=%r",
        idea_number, selected.get("run_id"), selected.get("idea", "")[:80],
    )
    return selected


# ---------------------------------------------------------------------------
# Progress / heartbeat poster for Slack
# ---------------------------------------------------------------------------

# Emoji map for section milestones
_SECTION_EMOJIS: dict[str, str] = {
    "executive_summary": ":memo:",
    "problem_statement": ":dart:",
    "user_personas": ":busts_in_silhouette:",
    "functional_requirements": ":gear:",
    "no_functional_requirements": ":shield:",
    "edge_cases": ":warning:",
    "error_handling": ":rotating_light:",
    "success_metrics": ":chart_with_upwards_trend:",
    "dependencies": ":link:",
    "assumptions": ":crystal_ball:",
}


def make_progress_poster(
    channel: str,
    thread_ts: str,
    user: str,
    send_tool,
    *,
    run_id: str = "",
) -> Callable[[str, dict], None]:
    """Return a ``progress_callback`` that posts heartbeat messages to Slack.

    The returned callable accepts ``(event_type, details)`` and translates
    each event into a concise Slack message in the user's thread.

    When *run_id* is provided, the crewJobs document is also updated
    with the ``current_section`` field so progress is queryable.
    """

    def _post(event_type: str, details: dict) -> None:
        msg: str | None = None

        # ── Orchestrator pipeline stage events ────────────────────
        if event_type == "pipeline_stage_start":
            stage = details.get("stage", "")
            desc = details.get("description", "")
            if stage == "idea_refinement":
                msg = ":bulb: Starting *Idea Refinement* — iterating until the idea is polished…"
            elif stage == "requirements_breakdown":
                msg = ":mag: Starting *Requirements Breakdown* — decomposing idea into detailed requirements…"
            else:
                msg = f":gear: Starting *{desc or stage}*…"

        elif event_type == "pipeline_stage_complete":
            stage = details.get("stage", "")
            iters = details.get("iterations", 0)
            if stage == "idea_refinement":
                msg = (
                    f":white_check_mark: *Idea Refinement* complete "
                    f"({iters} iteration(s)). Moving to requirements breakdown…"
                )
            elif stage == "requirements_breakdown":
                msg = (
                    f":white_check_mark: *Requirements Breakdown* complete "
                    f"({iters} iteration(s))."
                )
            else:
                msg = f":white_check_mark: *{stage}* complete ({iters} iteration(s))."

        elif event_type == "pipeline_stage_skipped":
            stage = details.get("stage", "")
            msg = f":fast_forward: *{stage}* skipped (already done or not needed)."

        elif event_type == "section_start":
            title = details.get("section_title", "")
            step = details.get("section_step", 0)
            total = details.get("total_sections", 0)
            emoji = _SECTION_EMOJIS.get(
                details.get("section_key", ""), ":hourglass_flowing_sand:",
            )
            msg = f"{emoji} [{step}/{total}] Starting _{title}_…"

            # Persist current section in the crewJobs document
            if run_id:
                try:
                    from crewai_productfeature_planner.mongodb.crew_jobs import (
                        update_job_status,
                    )
                    update_job_status(
                        run_id, "running",
                        current_section=title,
                        current_section_key=details.get("section_key", ""),
                        current_section_step=step,
                        total_sections=total,
                    )
                except Exception:  # noqa: BLE001
                    logger.debug(
                        "crewJobs section update failed for %s",
                        run_id, exc_info=True,
                    )

        elif event_type == "exec_summary_iteration":
            iteration = details.get("iteration", 0)
            max_iter = details.get("max_iterations", 0)
            msg = (
                f":writing_hand: Refining *Executive Summary*… "
                f"(iteration {iteration}/{max_iter})"
            )

        elif event_type == "executive_summary_complete":
            iters = details.get("iterations", 0)
            msg = (
                f":white_check_mark: *Executive Summary* complete "
                f"after {iters} iteration(s)."
            )

        elif event_type == "section_iteration":
            title = details.get("section_title", "")
            step = details.get("section_step", 0)
            total = details.get("total_sections", 0)
            iteration = details.get("iteration", 0)
            max_iter = details.get("max_iterations", 0)
            emoji = _SECTION_EMOJIS.get(
                details.get("section_key", ""), ":writing_hand:",
            )
            msg = (
                f"{emoji} [{step}/{total}] Refining _{title}_… "
                f"(iteration {iteration}/{max_iter})"
            )

        elif event_type == "section_complete":
            title = details.get("section_title", "")
            step = details.get("section_step", 0)
            total = details.get("total_sections", 0)
            iters = details.get("iterations", 0)
            emoji = _SECTION_EMOJIS.get(
                details.get("section_key", ""), ":white_check_mark:",
            )
            msg = (
                f"{emoji} [{step}/{total}] *{title}* complete "
                f"({iters} iteration(s))."
            )

        elif event_type == "all_sections_complete":
            msg = (
                ":tada: All PRD sections complete! "
                "Assembling the final document…"
            )

        elif event_type == "prd_complete":
            msg = ":rocket: *PRD generation complete!* Finalizing output…"

        elif event_type == "confluence_published":
            url = details.get("url", "")
            if url:
                msg = f":globe_with_meridians: *Confluence published!* <{url}|View PRD>"
            else:
                msg = ":globe_with_meridians: *Confluence published!*"

        elif event_type == "jira_published":
            count = details.get("ticket_count", 0)
            msg = f":tickets: *Jira tickets created!* ({count} ticket(s))"

        elif event_type == "jira_skeleton_start":
            msg = ":pencil: Generating Jira ticket skeleton (Epics & Stories outline)…"

        elif event_type == "jira_skeleton_ready":
            msg = (
                ":clipboard: *Jira skeleton ready!* "
                "Waiting for your approval before creating tickets…"
            )

        elif event_type == "jira_epics_stories_start":
            msg = ":hammer_and_wrench: Creating Jira Epics and Stories…"

        elif event_type == "jira_epics_stories_complete":
            msg = (
                ":white_check_mark: *Epics & Stories created!* "
                "Waiting for review before creating sub-tasks…"
            )

        elif event_type == "jira_subtasks_start":
            msg = ":gear: Creating detailed Jira sub-tasks with dependencies…"

        if msg:
            try:
                send_tool.run(channel=channel, text=msg, thread_ts=thread_ts)
            except Exception:  # noqa: BLE001
                logger.debug(
                    "Progress post failed for %s", event_type, exc_info=True,
                )

    return _post


# ---------------------------------------------------------------------------
# Non-interactive exec summary feedback gate
# ---------------------------------------------------------------------------

# Module-level state for non-interactive (auto-approve) flows that still
# want to pause after the executive summary to let the user iterate.
# Keyed by run_id → dict with channel, thread_ts, event, decision, feedback.
_pending_exec_feedback: dict[str, dict] = {}
_exec_feedback_lock = threading.Lock()


def resolve_exec_feedback(run_id: str, action: str, feedback_text: str | None = None) -> bool:
    """Signal a pending exec-summary feedback gate for *run_id*.

    Called by the interactions router (button click) or events router
    (thread reply).

    *action* is ``"approve"`` or ``"feedback"``.

    Returns ``True`` if the gate was found and signalled.
    """
    with _exec_feedback_lock:
        info = _pending_exec_feedback.get(run_id)
        if not info:
            return False
        info["decision"] = action
        info["feedback"] = feedback_text
        info["event"].set()
        return True


def make_exec_summary_gate(
    channel: str,
    thread_ts: str,
    user: str,
    send_tool,
    *,
    run_id: str = "",
) -> "Callable[[str, str, str, int], tuple[str, str | None]]":
    """Return an ``exec_summary_user_feedback_callback`` for auto-approve flows.

    Skips the pre-draft guidance prompt (iteration 0) and after each
    iteration posts the executive summary with Approve / Feedback buttons
    so the user can iterate or continue to PRD generation.
    """

    def _callback(
        content: str,
        idea: str,
        cb_run_id: str,
        iteration: int,
    ) -> tuple[str, str | None]:
        if iteration == 0:
            # Skip initial guidance — auto mode
            return ("skip", None)

        # Post the exec summary with feedback blocks
        from crewai_productfeature_planner.apis.slack.blocks import (
            exec_summary_feedback_blocks,
        )

        blocks = exec_summary_feedback_blocks(cb_run_id, content, iteration)
        try:
            from crewai_productfeature_planner.tools.slack_tools import _get_slack_client
            client = _get_slack_client()
            if client:
                client.chat_postMessage(
                    channel=channel,
                    thread_ts=thread_ts,
                    text=f"Executive Summary — Iteration {iteration}",
                    blocks=blocks,
                )
        except Exception:  # noqa: BLE001
            logger.debug("Failed to post exec summary feedback blocks", exc_info=True)

        # Register the pending gate
        gate_event = threading.Event()
        with _exec_feedback_lock:
            _pending_exec_feedback[cb_run_id] = {
                "channel": channel,
                "thread_ts": thread_ts,
                "user": user,
                "event": gate_event,
                "decision": None,
                "feedback": None,
            }

        # Wait for user response (10 minutes max)
        gate_event.wait(timeout=600.0)

        with _exec_feedback_lock:
            info = _pending_exec_feedback.pop(cb_run_id, {})

        decision = info.get("decision")
        feedback = info.get("feedback")

        if decision == "approve":
            logger.info(
                "[ExecSummaryGate] User approved at iteration %d for "
                "run_id=%s",
                iteration, cb_run_id,
            )
            return ("approve", None)

        if decision == "feedback" and feedback:
            logger.info(
                "[ExecSummaryGate] User feedback at iteration %d for "
                "run_id=%s (%d chars)",
                iteration, cb_run_id, len(feedback),
            )
            try:
                from crewai_productfeature_planner.tools.slack_tools import _get_slack_client
                client = _get_slack_client()
                if client:
                    client.chat_postMessage(
                        channel=channel,
                        thread_ts=thread_ts,
                        text=(
                            ":memo: Got it! Incorporating your feedback "
                            "into the next iteration\u2026"
                        ),
                    )
            except Exception:  # noqa: BLE001
                pass
            return ("feedback", feedback)

        # Timeout or unknown — auto-approve and continue
        logger.warning(
            "[ExecSummaryGate] Timeout for run_id=%s at iteration %d "
            "— auto-approving",
            cb_run_id, iteration,
        )
        try:
            send_tool.run(
                channel=channel,
                text=(
                    ":hourglass: No response received — auto-approving "
                    "executive summary and continuing to PRD generation."
                ),
                thread_ts=thread_ts,
            )
        except Exception:  # noqa: BLE001
            pass
        return ("approve", None)

    return _callback


# ---------------------------------------------------------------------------
# Non-interactive exec summary COMPLETION gate
# ---------------------------------------------------------------------------

# Module-level state for the phase gate between the executive summary
# and section-level drafting.  Keyed by run_id.
_pending_exec_completion: dict[str, dict] = {}
_exec_completion_lock = threading.Lock()


def resolve_exec_completion(run_id: str, action: str) -> bool:
    """Signal a pending exec-summary completion gate for *run_id*.

    Called by the interactions router when the user clicks
    "Continue to Sections" (``exec_summary_continue``) or "Stop"
    (``exec_summary_stop``).

    Returns ``True`` if the gate was found and signalled.
    """
    with _exec_completion_lock:
        info = _pending_exec_completion.get(run_id)
        if not info:
            return False
        info["decision"] = action
        info["event"].set()
        return True


def make_exec_summary_completion_gate(
    channel: str,
    thread_ts: str,
    user: str,
    send_tool,
    *,
    run_id: str = "",
) -> "Callable[[str, str, str, list[dict]], bool]":
    """Return an ``executive_summary_callback`` for auto-approve flows.

    Posts the finalized executive summary with Continue / Stop buttons
    so the user can review before the flow proceeds to section drafting.

    Returns ``True`` → continue to section drafting.
    Returns ``False`` → stop after executive summary.
    """

    def _callback(
        executive_summary: str,
        idea: str,
        cb_run_id: str,
        iterations: list[dict],
    ) -> bool:
        total_iterations = len(iterations)

        from crewai_productfeature_planner.apis.slack.blocks import (
            exec_summary_completion_blocks,
        )

        blocks = exec_summary_completion_blocks(
            cb_run_id, executive_summary, total_iterations,
        )
        try:
            from crewai_productfeature_planner.tools.slack_tools import _get_slack_client
            client = _get_slack_client()
            if client:
                client.chat_postMessage(
                    channel=channel,
                    thread_ts=thread_ts,
                    text="Executive Summary — Finalized — awaiting your review",
                    blocks=blocks,
                )
        except Exception:  # noqa: BLE001
            logger.debug("Failed to post exec summary completion blocks", exc_info=True)

        # Register the pending gate
        gate_event = threading.Event()
        with _exec_completion_lock:
            _pending_exec_completion[cb_run_id] = {
                "channel": channel,
                "thread_ts": thread_ts,
                "user": user,
                "event": gate_event,
                "decision": None,
            }

        # Wait for user response (10 minutes max)
        gate_event.wait(timeout=600.0)

        with _exec_completion_lock:
            info = _pending_exec_completion.pop(cb_run_id, {})

        decision = info.get("decision")

        if decision == "exec_summary_stop":
            logger.info(
                "[ExecCompletionGate] User chose to stop after exec "
                "summary for run_id=%s",
                cb_run_id,
            )
            return False

        if decision == "exec_summary_continue":
            logger.info(
                "[ExecCompletionGate] User approved continuation to "
                "sections for run_id=%s",
                cb_run_id,
            )
            return True

        # Timeout — auto-continue to sections
        logger.warning(
            "[ExecCompletionGate] Timeout for run_id=%s — "
            "auto-continuing to section drafting",
            cb_run_id,
        )
        try:
            send_tool.run(
                channel=channel,
                text=(
                    ":hourglass: No response received — auto-continuing "
                    "to section-level PRD drafting."
                ),
                thread_ts=thread_ts,
            )
        except Exception:  # noqa: BLE001
            pass
        return True

    return _callback


# ---------------------------------------------------------------------------
# Non-interactive requirements approval gate
# ---------------------------------------------------------------------------

# Module-level state for requirements approval in auto-approve flows.
# Keyed by run_id → dict with channel, thread_ts, event, decision.
_pending_requirements_approval: dict[str, dict] = {}
_requirements_approval_lock = threading.Lock()


def resolve_requirements_approval(run_id: str, action: str) -> bool:
    """Signal a pending requirements-approval gate for *run_id*.

    Called by the interactions router when the user clicks
    "Approve" (``requirements_approve``) or "Cancel"
    (``requirements_cancel``).

    Returns ``True`` if the gate was found and signalled.
    """
    with _requirements_approval_lock:
        info = _pending_requirements_approval.get(run_id)
        if not info:
            return False
        info["decision"] = action
        info["event"].set()
        return True


def make_requirements_approval_gate(
    channel: str,
    thread_ts: str,
    user: str,
    send_tool,
    *,
    run_id: str = "",
) -> "Callable[[str, str, str, list[dict] | None], bool]":
    """Return a ``requirements_approval_callback`` for auto-approve flows.

    Posts the requirements breakdown with Approve / Cancel buttons
    so the user can review before the flow proceeds to the executive
    summary and section drafting.

    Returns ``False`` → approved, continue to executive summary.
    Returns ``True``  → finalized/cancelled (raises RequirementsFinalized).
    """

    def _callback(
        requirements: str,
        idea: str,
        cb_run_id: str,
        breakdown_history: list[dict] | None = None,
    ) -> bool:
        iteration_count = len(breakdown_history) if breakdown_history else 0

        from crewai_productfeature_planner.apis.slack.blocks import (
            requirements_approval_blocks,
        )

        blocks = requirements_approval_blocks(
            cb_run_id, requirements, iteration_count,
        )
        try:
            from crewai_productfeature_planner.tools.slack_tools import _get_slack_client
            client = _get_slack_client()
            if client:
                client.chat_postMessage(
                    channel=channel,
                    thread_ts=thread_ts,
                    text="Requirements Breakdown Complete — awaiting your review",
                    blocks=blocks,
                )
        except Exception:  # noqa: BLE001
            logger.debug(
                "Failed to post requirements approval blocks", exc_info=True,
            )

        # Register the pending gate
        gate_event = threading.Event()
        with _requirements_approval_lock:
            _pending_requirements_approval[cb_run_id] = {
                "channel": channel,
                "thread_ts": thread_ts,
                "user": user,
                "event": gate_event,
                "decision": None,
            }

        # Wait for user response (10 minutes max)
        gate_event.wait(timeout=600.0)

        with _requirements_approval_lock:
            info = _pending_requirements_approval.pop(cb_run_id, {})

        decision = info.get("decision")

        if decision == "requirements_cancel":
            logger.info(
                "[RequirementsGate] User cancelled requirements for "
                "run_id=%s",
                cb_run_id,
            )
            return True  # finalize → raises RequirementsFinalized

        if decision == "requirements_approve":
            logger.info(
                "[RequirementsGate] User approved requirements for "
                "run_id=%s",
                cb_run_id,
            )
            return False  # continue to executive summary

        # Timeout — auto-approve to avoid blocking forever
        logger.warning(
            "[RequirementsGate] Timeout for run_id=%s — "
            "auto-approving requirements",
            cb_run_id,
        )
        try:
            send_tool.run(
                channel=channel,
                text=(
                    ":hourglass: No response received — auto-approving "
                    "requirements and continuing to executive summary."
                ),
                thread_ts=thread_ts,
            )
        except Exception:  # noqa: BLE001
            pass
        return False

    return _callback


# ---------------------------------------------------------------------------
# Publish intent handlers
# ---------------------------------------------------------------------------


def handle_publish_intent(channel: str, thread_ts: str, user: str, send_tool) -> None:
    """Publish all pending PRDs to Confluence and create Jira tickets."""
    ack = (
        f"<@{user}> :gear: Publishing all pending PRDs to Confluence and "
        "creating Jira tickets… I'll post the results shortly."
    )
    send_tool.run(channel=channel, text=ack, thread_ts=thread_ts)
    append_to_thread(channel, thread_ts, "assistant", ack)

    try:
        from crewai_productfeature_planner.apis.publishing.service import (
            publish_all_and_create_tickets,
        )

        result = publish_all_and_create_tickets()

        conf = result.get("confluence", {})
        jira = result.get("jira", {})

        lines = [f"<@{user}> :white_check_mark: *Publishing complete!*\n"]

        # Confluence summary
        pub_count = conf.get("published", 0)
        pub_fail = conf.get("failed", 0)
        if pub_count or pub_fail:
            lines.append(f"*Confluence:* {pub_count} published, {pub_fail} failed")
            for r in conf.get("results", []):
                lines.append(f"  • _{r.get('title', '')}_ → <{r.get('url', '')}|View>")
        else:
            msg = conf.get("message", "No pending PRDs to publish")
            lines.append(f"*Confluence:* {msg}")

        # Jira summary
        jira_count = jira.get("completed", 0)
        jira_fail = jira.get("failed", 0)
        if jira_count or jira_fail:
            lines.append(f"*Jira:* {jira_count} completed, {jira_fail} failed")
            for r in jira.get("results", []):
                keys = r.get("ticket_keys", [])
                if keys:
                    lines.append(f"  • run `{r.get('run_id', '')[:8]}…` → {', '.join(keys)}")
        else:
            msg = jira.get("message", "No pending Jira deliveries")
            lines.append(f"*Jira:* {msg}")

        # Next-step: offer Jira button when Confluence was published
        # but no Jira tickets were created.
        if pub_count and not jira_count:
            # Find a run_id from the just-published results
            published_results = conf.get("results", [])
            button_run_id = ""
            if published_results:
                button_run_id = published_results[0].get("run_id", "")

            if button_run_id:
                from crewai_productfeature_planner.apis.slack.blocks import (
                    jira_only_blocks,
                )
                from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

                jira_blocks = jira_only_blocks(button_run_id)
                client = _get_slack_client()
                if client and jira_blocks:
                    try:
                        client.chat_postMessage(
                            channel=channel,
                            thread_ts=thread_ts,
                            blocks=jira_blocks,
                            text="Create Jira Tickets",
                        )
                    except Exception as exc:
                        logger.debug("Jira next-step button post failed: %s", exc)

        summary = "\n".join(lines)
        send_tool.run(channel=channel, text=summary, thread_ts=thread_ts)
        append_to_thread(channel, thread_ts, "assistant", summary)

    except Exception as exc:
        err_msg = f"<@{user}> :x: Publishing failed: {exc}"
        send_tool.run(channel=channel, text=err_msg, thread_ts=thread_ts)
        append_to_thread(channel, thread_ts, "assistant", err_msg)
        logger.error("Publish intent failed: %s", exc)


def handle_check_publish_intent(channel: str, thread_ts: str, user: str, send_tool) -> None:
    """Check and report the publishing status of pending PRDs."""
    try:
        from crewai_productfeature_planner.apis.publishing.service import (
            list_pending_prds,
        )

        items = list_pending_prds()

        if not items:
            msg = (
                f"<@{user}> :white_check_mark: All clear! "
                "No PRDs pending Confluence publishing or Jira ticket creation."
            )
            send_tool.run(channel=channel, text=msg, thread_ts=thread_ts)
            append_to_thread(channel, thread_ts, "assistant", msg)
            return

        lines = [f"<@{user}> :clipboard: *Pending PRD Deliveries* ({len(items)} total)\n"]
        for item in items:
            rid = item.get("run_id", "disk")[:8]
            title = item.get("title", "Untitled")
            conf = ":white_check_mark:" if item.get("confluence_published") else ":x:"
            jira = ":white_check_mark:" if item.get("jira_completed") else ":x:"
            lines.append(f"  • `{rid}…` _{title}_ — Confluence {conf}  Jira {jira}")

        msg = "\n".join(lines)
        send_tool.run(channel=channel, text=msg, thread_ts=thread_ts)
        append_to_thread(channel, thread_ts, "assistant", msg)

        # Post an interactive Publish button below the status list
        first_run_id = ""
        for item in items:
            r = item.get("run_id", "")
            if r:
                first_run_id = r
                break
        if first_run_id:
            from crewai_productfeature_planner.apis.slack.blocks import (
                publish_only_blocks,
            )
            from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

            pub_blocks = publish_only_blocks(first_run_id)
            client = _get_slack_client()
            if client and pub_blocks:
                try:
                    client.chat_postMessage(
                        channel=channel,
                        thread_ts=thread_ts,
                        blocks=pub_blocks,
                        text="Publish to Confluence",
                    )
                except Exception as exc:
                    logger.debug("Publish button post failed: %s", exc)

    except Exception as exc:
        err_msg = f"<@{user}> :x: Failed to check publishing status: {exc}"
        send_tool.run(channel=channel, text=err_msg, thread_ts=thread_ts)
        append_to_thread(channel, thread_ts, "assistant", err_msg)
        logger.error("Check publish intent failed: %s", exc)


# ---------------------------------------------------------------------------
# Create Jira tickets (text intent – no run_id yet)
# ---------------------------------------------------------------------------


def handle_create_jira_intent(
    channel: str, thread_ts: str, user: str, send_tool
) -> None:
    """Find the latest completed PRD and kick off the Jira skeleton phase.

    When the user types "create jira" in Slack (text intent), there is
    no ``run_id`` attached.  We resolve it by looking for the most recent
    completed product in the active project, or — if no project session
    is active — the most recent completed product in the channel.
    """
    try:
        # Attempt to resolve the project from the session
        from crewai_productfeature_planner.apis.slack.session_manager import (
            get_context_session,
        )
        from crewai_productfeature_planner.mongodb.working_ideas import (
            find_completed_ideas_by_project,
            find_unfinalized,
        )

        session = get_context_session(user, channel)
        project_id = session.get("project_id") if session else None

        run_id: str | None = None

        # 1. Look in completed products for the project
        if project_id:
            products = find_completed_ideas_by_project(
                project_id, channel=channel,
            )
            if products:
                run_id = products[0].get("run_id")

        # 2. Fallback: look for the most recent unfinalized run
        if not run_id:
            unfinalized = find_unfinalized()
            if project_id:
                unfinalized = [
                    r for r in unfinalized
                    if r.get("project_id") == project_id
                ] or unfinalized
            if unfinalized:
                run_id = unfinalized[0].get("run_id")

        if not run_id:
            send_tool.run(
                channel=channel,
                thread_ts=thread_ts,
                text=(
                    f"<@{user}> :no_entry_sign: No completed PRD found to "
                    "create Jira tickets for. Run a PRD flow first!"
                ),
            )
            append_to_thread(
                channel, thread_ts, "assistant", "(no completed PRD for Jira)"
            )
            return

        # Delegate to the delivery action handler
        from crewai_productfeature_planner.apis.slack.interactions_router._delivery_action_handler import (
            _do_create_jira,
        )

        _do_create_jira(run_id, user, channel, thread_ts)

    except Exception as exc:
        err_msg = f"<@{user}> :x: Failed to create Jira tickets: {exc}"
        send_tool.run(channel=channel, text=err_msg, thread_ts=thread_ts)
        append_to_thread(channel, thread_ts, "assistant", err_msg)
        logger.error("Create Jira intent failed: %s", exc)


# ---------------------------------------------------------------------------
# Resume PRD flow from Slack
# ---------------------------------------------------------------------------


def handle_resume_prd(
    channel: str,
    thread_ts: str,
    user: str,
    send_tool,
    project_id: str | None = None,
    idea_number: int | None = None,
) -> None:
    """Find the latest resumable PRD run and resume it in a background thread.

    If *idea_number* is provided (1-based), the numbered idea from
    the project idea list is selected instead of the most recent
    unfinalized run.

    If no resumable run exists, tells the user.
    """
    try:
        # When a specific idea number is given, resolve via the project
        # idea list (same ordering as handle_list_ideas) so the user
        # can say "resume idea #2" after viewing the list.
        if idea_number is not None and project_id:
            run_info = _resolve_idea_by_number(
                idea_number, project_id, channel, thread_ts, user, send_tool,
            )
            if run_info is None:
                return  # error already posted
        else:
            from crewai_productfeature_planner.mongodb import find_unfinalized

            unfinalized = find_unfinalized()

            # Filter to the active project if available
            if project_id:
                project_runs = [
                    r for r in unfinalized
                    if r.get("project_id") == project_id
                ]
                if project_runs:
                    unfinalized = project_runs

            if not unfinalized:
                send_tool.run(
                    channel=channel,
                    text=(
                        f"<@{user}> :no_entry_sign: No paused or resumable PRD "
                        "runs found. Start a new one by telling me your idea!"
                    ),
                    thread_ts=thread_ts,
                )
                append_to_thread(channel, thread_ts, "assistant",
                                 "(no resumable runs)")
                return

            # Pick the most recent run
            run_info = unfinalized[0]
        run_id = run_info["run_id"]
        idea = run_info.get("idea") or "(unknown idea)"
        status = run_info.get("status", "unknown")
        sections_done = run_info.get("sections_done", 0)
        total_sections = run_info.get("total_sections", 10)

        # A completed idea cannot be resumed — suggest rescan instead.
        if status == "completed":
            send_tool.run(
                channel=channel,
                text=(
                    f"<@{user}> :white_check_mark: That idea is already "
                    f"completed! Use *Rescan* to start a fresh PRD flow "
                    f"with the same idea, or tell me a new idea."
                ),
                thread_ts=thread_ts,
            )
            append_to_thread(channel, thread_ts, "assistant",
                             "(idea already completed — suggested rescan)")
            return

        idea_preview = idea[:500] + "…" if len(idea) > 500 else idea
        ack = (
            f"<@{user}> :arrows_counterclockwise: Resuming PRD flow "
            f"(run `{run_id}`):\n"
            f"> _{idea_preview}_\n"
            f"Progress: {sections_done}/{total_sections} sections completed. "
            "I'll continue from where it paused."
        )
        send_tool.run(channel=channel, text=ack, thread_ts=thread_ts)
        append_to_thread(channel, thread_ts, "assistant", ack)

        # Run the resume in a background thread
        from crewai_productfeature_planner.apis.prd.service import resume_prd_flow
        from crewai_productfeature_planner.apis.shared import FlowRun, FlowStatus, runs
        from crewai_productfeature_planner.tools.slack_tools import (
            SlackPostPRDResultTool,
        )

        if run_id not in runs:
            runs[run_id] = FlowRun(run_id=run_id, flow_name="prd")

        # Update Slack context in case thread changed
        try:
            from crewai_productfeature_planner.mongodb.working_ideas.repository import (
                save_slack_context,
            )
            save_slack_context(run_id, channel, thread_ts, idea=idea)
        except Exception:  # noqa: BLE001
            logger.debug("save_slack_context failed for %s", run_id, exc_info=True)

        # Build progress callback for live heartbeat messages
        progress_cb = make_progress_poster(
            channel=channel,
            thread_ts=thread_ts,
            user=user,
            send_tool=send_tool,
            run_id=run_id,
        )

        # Build exec summary user feedback gate so the user can
        # iterate or approve each executive summary revision.
        exec_summary_cb = make_exec_summary_gate(
            channel=channel,
            thread_ts=thread_ts,
            user=user,
            send_tool=send_tool,
            run_id=run_id,
        )

        # Build exec summary completion gate (Phase 1 → Phase 2 pause)
        exec_completion_cb = make_exec_summary_completion_gate(
            channel=channel,
            thread_ts=thread_ts,
            user=user,
            send_tool=send_tool,
            run_id=run_id,
        )

        # Build requirements approval gate so the user can review
        # the requirements breakdown before proceeding.
        requirements_cb = make_requirements_approval_gate(
            channel=channel,
            thread_ts=thread_ts,
            user=user,
            send_tool=send_tool,
            run_id=run_id,
        )

        def _resume_and_notify():
            try:
                resume_prd_flow(
                    run_id,
                    auto_approve=True,
                    progress_callback=progress_cb,
                    exec_summary_user_feedback_callback=exec_summary_cb,
                    executive_summary_callback=exec_completion_cb,
                    requirements_approval_callback=requirements_cb,
                )

                run = runs.get(run_id)
                if run and run.status == FlowStatus.COMPLETED:
                    post_tool = SlackPostPRDResultTool()
                    post_tool.run(
                        channel=channel,
                        idea=idea,
                        output_file=run.output_file,
                        confluence_url=run.confluence_url,
                        jira_output=run.jira_output,
                        thread_ts=thread_ts,
                        run_id=run_id,
                    )
                elif run and run.status == FlowStatus.PAUSED:
                    from crewai_productfeature_planner.apis.slack.blocks import flow_paused_blocks
                    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

                    reason = run.error or ""
                    blocks = flow_paused_blocks(run_id, reason)
                    client = _get_slack_client()
                    if client:
                        try:
                            client.chat_postMessage(
                                channel=channel,
                                thread_ts=thread_ts,
                                blocks=blocks,
                                text=f"PRD flow paused again ({run_id})",
                            )
                        except Exception:
                            logger.debug("Failed to post pause blocks", exc_info=True)
                            send_tool.run(
                                channel=channel,
                                text=(
                                    f":pause_button: PRD flow paused again "
                                    f"(run `{run_id}`). Say *resume prd flow* to retry."
                                ),
                                thread_ts=thread_ts,
                            )
                    else:
                        send_tool.run(
                            channel=channel,
                            text=(
                                f":pause_button: PRD flow paused again "
                                f"(run `{run_id}`). Say *resume prd flow* to retry."
                            ),
                            thread_ts=thread_ts,
                        )
                else:
                    error_msg = run.error if run else "Unknown error"
                    send_tool.run(
                        channel=channel,
                        text=f":x: PRD flow failed: {error_msg}",
                        thread_ts=thread_ts,
                    )
            except Exception as exc:
                logger.error("Resume PRD flow %s failed: %s", run_id, exc)
                try:
                    send_tool.run(
                        channel=channel,
                        text=f":x: Failed to resume PRD flow: {exc}",
                        thread_ts=thread_ts,
                    )
                except Exception:
                    pass
            except BaseException as exc:  # noqa: BLE001
                logger.critical(
                    "Resume PRD flow %s caught fatal %s: %s — "
                    "suppressed to protect server",
                    run_id, type(exc).__name__, exc,
                )

        t = threading.Thread(
            target=_resume_and_notify,
            name=f"slack-prd-resume-{run_id}",
            daemon=True,
        )
        t.start()
        logger.info(
            "Slack PRD resume started for run_id=%s in thread %s/%s",
            run_id, channel, thread_ts,
        )

    except Exception as exc:
        err_msg = f"<@{user}> :x: Failed to resume PRD flow: {exc}"
        send_tool.run(channel=channel, text=err_msg, thread_ts=thread_ts)
        append_to_thread(channel, thread_ts, "assistant", err_msg)
        logger.error("Resume PRD intent failed: %s", exc)


# ---------------------------------------------------------------------------
# Restart PRD flow from Slack
# ---------------------------------------------------------------------------


def handle_restart_prd(
    channel: str,
    thread_ts: str,
    user: str,
    send_tool,
    event_ts: str,
    project_id: str | None = None,
    idea_number: int | None = None,
) -> None:
    """Archive the current PRD run and start a fresh flow with the same idea.

    Posts a confirmation prompt (Block Kit buttons) before proceeding.
    If the user confirms, the current run is archived and a new flow
    starts.  If the user cancels, no changes are made.

    If *idea_number* is provided (1-based), the numbered idea from
    the project idea list is selected instead of the most recent
    unfinalized run.

    If no resumable run exists, tells the user.
    """
    try:
        # When a specific idea number is given, resolve via the project
        # idea list (same ordering as handle_list_ideas).
        if idea_number is not None and project_id:
            run_info = _resolve_idea_by_number(
                idea_number, project_id, channel, thread_ts, user, send_tool,
            )
            if run_info is None:
                return  # error already posted
        else:
            from crewai_productfeature_planner.mongodb import find_unfinalized

            unfinalized = find_unfinalized()

            # Filter to the active project if available
            if project_id:
                project_runs = [
                    r for r in unfinalized
                    if r.get("project_id") == project_id
                ]
                if project_runs:
                    unfinalized = project_runs

            if not unfinalized:
                send_tool.run(
                    channel=channel,
                    text=(
                        f"<@{user}> :no_entry_sign: No active PRD runs found "
                        "to restart. Start a new one by telling me your idea!"
                    ),
                    thread_ts=thread_ts,
                )
                append_to_thread(channel, thread_ts, "assistant",
                                 "(no runs to restart)")
                return

            # Pick the most recent run
            run_info = unfinalized[0]
        run_id = run_info["run_id"]
        idea = run_info.get("idea") or "(unknown idea)"
        sections_done = run_info.get("sections_done", 0)
        total_sections = run_info.get("total_sections", 10)

        # Post confirmation buttons
        from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

        client = _get_slack_client()
        if not client:
            send_tool.run(
                channel=channel,
                text=f"<@{user}> :x: Slack client unavailable.",
                thread_ts=thread_ts,
            )
            return

        # Slack section blocks have a 3000-char limit for the text field.
        # Truncate the idea to keep the entire block safely under the limit.
        idea_preview = idea[:500] + "…" if len(idea) > 500 else idea

        confirm_blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"<@{user}> :warning: *Restart PRD Flow?*\n\n"
                        f"This will *archive* the current run "
                        f"(`{run_id}`) and start a *brand new* PRD flow "
                        f"with the same idea:\n"
                        f"> _{idea_preview}_\n\n"
                        f"Progress so far: {sections_done}/{total_sections} "
                        f"sections completed.\n"
                        f"The archived run will remain available for reference."
                    ),
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Yes, restart"},
                        "style": "danger",
                        "action_id": "restart_prd_confirm",
                        "value": run_id,
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Cancel"},
                        "action_id": "restart_prd_cancel",
                        "value": run_id,
                    },
                ],
            },
        ]

        client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text="Restart PRD flow?",
            blocks=confirm_blocks,
        )
        append_to_thread(channel, thread_ts, "assistant",
                         "(restart confirmation prompt)")
        logger.info(
            "Posted restart confirmation for run_id=%s idea=%r",
            run_id, idea[:80],
        )

    except Exception as exc:
        err_msg = f"<@{user}> :x: Failed to process restart request: {exc}"
        send_tool.run(channel=channel, text=err_msg, thread_ts=thread_ts)
        append_to_thread(channel, thread_ts, "assistant", err_msg)
        logger.error("Restart PRD intent failed: %s", exc)


def execute_restart_prd(
    run_id: str,
    channel: str,
    thread_ts: str,
    user: str,
    event_ts: str = "",
    project_id: str | None = None,
) -> None:
    """Archive the given run and kick off a new PRD flow with its idea.

    Called after the user confirms the restart via the confirmation button.
    """
    try:
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            find_run_any_status,
            mark_archived,
        )
        from crewai_productfeature_planner.tools.slack_tools import (
            SlackSendMessageTool,
        )

        # Re-fetch the run to get the idea — use find_run_any_status so
        # completed runs are included (the user can legitimately restart
        # a finished idea from the idea list).
        doc = find_run_any_status(run_id)

        if not doc:
            send_tool = SlackSendMessageTool()
            send_tool.run(
                channel=channel,
                text=(
                    f"<@{user}> :x: Could not find run `{run_id}` — "
                    "it may have already been archived."
                ),
                thread_ts=thread_ts,
            )
            return

        idea = (
            doc.get("idea")
            or doc.get("finalized_idea")
            or "(unknown idea)"
        )
        project_id = project_id or doc.get("project_id")

        # Archive the old run
        mark_archived(run_id)

        # Also mark the crew job as archived
        try:
            from crewai_productfeature_planner.mongodb.crew_jobs.repository import (
                update_job_status,
            )
            update_job_status(run_id, "archived")
        except Exception:
            logger.debug("Could not archive crewJob for %s", run_id, exc_info=True)

        send_tool = SlackSendMessageTool()
        idea_preview = idea[:500] + "…" if len(idea) > 500 else idea
        send_tool.run(
            channel=channel,
            text=(
                f"<@{user}> :file_folder: Archived run `{run_id}`.\n"
                f":rocket: Starting a fresh PRD flow for:\n> _{idea_preview}_"
            ),
            thread_ts=thread_ts,
        )
        append_to_thread(channel, thread_ts, "assistant",
                         f"(archived {run_id}, starting fresh)")

        # Kick off a new flow with the same idea
        kick_off_prd_flow(
            channel=channel,
            thread_ts=thread_ts,
            user=user,
            idea=idea,
            event_ts=event_ts,
            project_id=project_id,
        )

    except Exception as exc:
        logger.error("execute_restart_prd failed for %s: %s", run_id, exc)
        try:
            send_tool = SlackSendMessageTool()
            send_tool.run(
                channel=channel,
                text=f"<@{user}> :x: Failed to restart PRD flow: {exc}",
                thread_ts=thread_ts,
            )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Archive idea (manual archive from idea list)
# ---------------------------------------------------------------------------


def handle_archive_idea(
    channel: str,
    thread_ts: str,
    user: str,
    send_tool,
    project_id: str | None = None,
    idea_number: int | None = None,
) -> None:
    """Post a confirmation prompt to archive a specific idea.

    If *idea_number* is provided (1-based), the numbered idea from
    the project idea list is selected.  Otherwise the most recent
    unfinalized run is used.

    Posts Block Kit buttons — the user must confirm before the idea
    is actually archived.
    """
    try:
        if idea_number is not None and project_id:
            run_info = _resolve_idea_by_number(
                idea_number, project_id, channel, thread_ts, user, send_tool,
            )
            if run_info is None:
                return
        else:
            from crewai_productfeature_planner.mongodb import find_unfinalized

            unfinalized = find_unfinalized()
            if project_id:
                project_runs = [
                    r for r in unfinalized
                    if r.get("project_id") == project_id
                ]
                if project_runs:
                    unfinalized = project_runs

            if not unfinalized:
                send_tool.run(
                    channel=channel,
                    text=(
                        f"<@{user}> :no_entry_sign: No active ideas found "
                        "to archive."
                    ),
                    thread_ts=thread_ts,
                )
                append_to_thread(channel, thread_ts, "assistant",
                                 "(no ideas to archive)")
                return

            run_info = unfinalized[0]

        run_id = run_info["run_id"]
        idea = run_info.get("idea") or "(unknown idea)"
        status = run_info.get("status", "unknown")

        from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

        client = _get_slack_client()
        if not client:
            send_tool.run(
                channel=channel,
                text=f"<@{user}> :x: Slack client unavailable.",
                thread_ts=thread_ts,
            )
            return

        idea_preview = idea[:500] + "\u2026" if len(idea) > 500 else idea

        confirm_blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"<@{user}> :file_folder: *Archive this idea?*\n\n"
                        f"This will archive the run (`{run_id}`) and "
                        f"remove it from your active idea list:\n"
                        f"> _{idea_preview}_\n\n"
                        f"Current status: *{status}*\n"
                        f"The archived idea will be preserved for reference "
                        f"but will no longer appear in your list."
                    ),
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Yes, archive"},
                        "action_id": "archive_idea_confirm",
                        "value": run_id,
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Cancel"},
                        "action_id": "archive_idea_cancel",
                        "value": run_id,
                    },
                ],
            },
        ]

        client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text="Archive this idea?",
            blocks=confirm_blocks,
        )
        append_to_thread(channel, thread_ts, "assistant",
                         "(archive confirmation prompt)")
        logger.info(
            "Posted archive confirmation for run_id=%s idea=%r",
            run_id, idea[:80],
        )

    except Exception as exc:
        err_msg = f"<@{user}> :x: Failed to process archive request: {exc}"
        send_tool.run(channel=channel, text=err_msg, thread_ts=thread_ts)
        append_to_thread(channel, thread_ts, "assistant", err_msg)
        logger.error("Archive idea intent failed: %s", exc)


def execute_archive_idea(
    run_id: str,
    channel: str,
    thread_ts: str,
    user: str,
) -> None:
    """Archive the given run after the user confirms.

    Marks both the working-idea document and the crew job as archived.
    """
    try:
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            find_run_any_status,
            mark_archived,
        )
        from crewai_productfeature_planner.tools.slack_tools import (
            SlackSendMessageTool,
        )

        doc = find_run_any_status(run_id)

        if not doc:
            send_tool = SlackSendMessageTool()
            send_tool.run(
                channel=channel,
                text=(
                    f"<@{user}> :x: Could not find run `{run_id}` \u2014 "
                    "it may have already been archived."
                ),
                thread_ts=thread_ts,
            )
            return

        idea = (
            doc.get("idea")
            or doc.get("finalized_idea")
            or "(unknown idea)"
        )

        # Archive the working-idea document
        mark_archived(run_id)

        # Also mark the crew job as archived
        try:
            from crewai_productfeature_planner.mongodb.crew_jobs.repository import (
                update_job_status,
            )
            update_job_status(run_id, "archived")
        except Exception:
            logger.debug("Could not archive crewJob for %s", run_id, exc_info=True)

        idea_preview = idea[:500] + "\u2026" if len(idea) > 500 else idea
        send_tool = SlackSendMessageTool()
        send_tool.run(
            channel=channel,
            text=(
                f"<@{user}> :white_check_mark: Archived run `{run_id}`.\n"
                f"> _{idea_preview}_\n"
                "The idea has been removed from your active list."
            ),
            thread_ts=thread_ts,
        )
        append_to_thread(channel, thread_ts, "assistant",
                         f"(archived {run_id})")
        logger.info("Archived idea run_id=%s by user=%s", run_id, user)

    except Exception as exc:
        logger.error("execute_archive_idea failed for %s: %s", run_id, exc)
        try:
            send_tool = SlackSendMessageTool()
            send_tool.run(
                channel=channel,
                text=f"<@{user}> :x: Failed to archive idea: {exc}",
                thread_ts=thread_ts,
            )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# PRD flow kickoff
# ---------------------------------------------------------------------------


def kick_off_prd_flow(
    *,
    channel: str,
    thread_ts: str,
    user: str,
    idea: str,
    event_ts: str,
    interactive: bool = False,
    project_id: str | None = None,
) -> None:
    """Start a PRD flow from a Slack interaction.

    When *interactive* is ``True``, the flow mirrors the CLI experience:
    refinement mode choice, idea approval, and requirements approval are
    all presented as Block Kit button prompts in the thread before
    sections are auto-generated.

    When ``False`` (the default), the flow runs with ``auto_approve=True``
    as before.

    If *project_id* is provided the working-idea document will be linked
    to the project so publishing can resolve project-level keys.
    """
    from crewai_productfeature_planner.apis.slack.router import _run_slack_prd_flow
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if client:
        try:
            client.reactions_add(channel=channel, timestamp=event_ts, name="eyes")
        except Exception:
            pass

    run_id = uuid.uuid4().hex[:12]

    if interactive:
        from crewai_productfeature_planner.apis.slack.interactive_handlers import (
            run_interactive_slack_flow,
        )
        t = threading.Thread(
            target=run_interactive_slack_flow,
            args=(run_id, idea, channel, thread_ts, user),
            kwargs={"project_id": project_id},
            name=f"slack-prd-interactive-{run_id}",
            daemon=True,
        )
    else:
        t = threading.Thread(
            target=_run_slack_prd_flow,
            args=(run_id, idea, channel, thread_ts),
            kwargs={"project_id": project_id} if project_id else {},
            name=f"slack-prd-{run_id}",
            daemon=True,
        )
    t.start()
