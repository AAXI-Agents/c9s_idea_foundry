"""PRDFlow callback factories for Slack interactive approval gates."""

from __future__ import annotations

import logging

from crewai_productfeature_planner.apis.slack.interactive_handlers._run_state import (
    _lock,
    _manual_refinement_text,
    get_interactive_run,
)
from crewai_productfeature_planner.apis.slack.interactive_handlers._slack_helpers import (
    _post_blocks,
    _wait_for_decision,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Refinement mode selection
# ---------------------------------------------------------------------------


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


def make_slack_exec_summary_feedback_callback(run_id: str):
    """Create an ``exec_summary_user_feedback_callback`` that prompts via Slack.

    Returns a callable matching the signature:
        ``(content, idea, run_id, iteration) -> (action, feedback_text)``

    At iteration 0 (pre-draft), posts a "provide guidance or skip" prompt.
    At iteration >= 1 (post-iteration), shows the current summary and waits
    for the user to approve or reply in-thread with feedback.
    """
    from crewai_productfeature_planner.apis.slack.blocks import (
        exec_summary_feedback_blocks,
        exec_summary_pre_feedback_blocks,
    )

    def _callback(
        content: str,
        idea: str,
        cb_run_id: str,
        iteration: int,
    ) -> tuple[str, str | None]:
        info = get_interactive_run(run_id)
        if not info:
            # No interactive session — skip feedback
            return ("skip", None)

        if info.get("cancelled"):
            return ("approve", None)

        channel = info["channel"]
        thread_ts = info["thread_ts"]

        if iteration == 0:
            # ── Pre-draft: provide guidance or skip ──
            blocks = exec_summary_pre_feedback_blocks(run_id, idea)
            _post_blocks(
                channel, thread_ts, blocks,
                text="Executive Summary — provide initial guidance?",
            )
        else:
            # ── Post-iteration: show summary, approve or feedback ──
            blocks = exec_summary_feedback_blocks(run_id, content, iteration)
            _post_blocks(
                channel, thread_ts, blocks,
                text=f"Executive Summary — Iteration {iteration}",
            )

        # Wait for either a button click or a thread reply
        action_type = (
            "exec_summary_pre_feedback" if iteration == 0
            else "exec_summary_feedback"
        )
        with _lock:
            info["pending_action"] = action_type
            info["decision"] = None
            info["event"].clear()
            _manual_refinement_text.pop(run_id, None)

        info["event"].wait(timeout=600.0)
        decision = info.get("decision")

        # Check for thread reply (user feedback text)
        with _lock:
            revised_text = _manual_refinement_text.pop(run_id, None)

        if decision == "exec_summary_approve":
            logger.info(
                "Exec summary approved by user at iteration %d for run_id=%s",
                iteration, run_id,
            )
            return ("approve", None)

        if decision in ("flow_cancel", "idea_cancel"):
            info["cancelled"] = True
            from crewai_productfeature_planner.flows.prd_flow import (
                ExecutiveSummaryCompleted,
            )
            raise ExecutiveSummaryCompleted("Cancelled via Slack by user")

        if decision == "exec_summary_skip":
            logger.info(
                "Exec summary initial guidance skipped for run_id=%s",
                run_id,
            )
            return ("skip", None)

        if revised_text:
            logger.info(
                "Exec summary user feedback at iteration %d for "
                "run_id=%s (%d chars)",
                iteration, run_id, len(revised_text),
            )
            return ("feedback", revised_text)

        # Timeout or unknown — skip feedback and continue normally
        logger.warning(
            "Exec summary feedback timeout for run_id=%s at "
            "iteration %d — skipping",
            run_id, iteration,
        )
        return ("skip", None)

    return _callback


# ---------------------------------------------------------------------------
# Executive summary completion gate (Phase 1 → Phase 2)
# ---------------------------------------------------------------------------


def make_slack_exec_summary_completion_callback(run_id: str):
    """Create an ``executive_summary_callback`` for interactive flows.

    Returns a callable: ``(executive_summary, idea, run_id, iterations) -> bool``
    where ``True`` means continue to section drafting and ``False`` means stop.

    Posts the finalized executive summary with Continue / Stop buttons
    so the user can review before the flow proceeds to Phase 2.
    """
    from crewai_productfeature_planner.apis.slack.blocks import (
        exec_summary_completion_blocks,
    )

    def _callback(
        executive_summary: str,
        idea: str,
        cb_run_id: str,
        iterations: list[dict],
    ) -> bool:
        info = get_interactive_run(run_id)
        if not info:
            # No interactive session — auto-continue
            return True

        if info.get("cancelled"):
            return False

        channel = info["channel"]
        thread_ts = info["thread_ts"]
        total_iterations = len(iterations)

        blocks = exec_summary_completion_blocks(
            run_id, executive_summary, total_iterations,
        )
        _post_blocks(
            channel, thread_ts, blocks,
            text="Executive Summary — Finalized — awaiting your review",
        )

        decision = _wait_for_decision(run_id, "exec_summary_completion")

        if decision == "exec_summary_continue":
            logger.info(
                "Exec summary completion: user chose to continue to "
                "section drafting for run_id=%s",
                run_id,
            )
            return True

        if decision == "exec_summary_stop":
            logger.info(
                "Exec summary completion: user chose to stop after "
                "executive summary for run_id=%s",
                run_id,
            )
            return False

        # Timeout — auto-continue
        logger.warning(
            "Exec summary completion timeout for run_id=%s — "
            "auto-continuing to section drafting",
            run_id,
        )
        return True

    return _callback


# ---------------------------------------------------------------------------
# Jira phased callbacks
# ---------------------------------------------------------------------------


def make_slack_jira_skeleton_callback(run_id: str):
    """Create a ``jira_skeleton_approval_callback`` that prompts via Slack.

    Returns a callable: ``(skeleton_text, run_id) -> (action, edited)``
    where action is ``"approve"`` or ``"reject"``.
    """
    from crewai_productfeature_planner.apis.slack.blocks import (
        jira_skeleton_approval_blocks,
    )

    def _callback(
        skeleton_text: str,
        cb_run_id: str,
    ) -> tuple[str, str | None]:
        info = get_interactive_run(run_id)
        if not info:
            return ("approve", None)

        blocks = jira_skeleton_approval_blocks(run_id, skeleton_text)
        _post_blocks(
            info["channel"], info["thread_ts"], blocks,
            text="Jira Ticket Skeleton — approve or skip?",
        )

        decision = _wait_for_decision(run_id, "jira_skeleton_approval")

        if decision == "jira_skeleton_approve":
            logger.info("Jira skeleton approved for run_id=%s", run_id)
            return ("approve", None)

        if decision == "jira_skeleton_reject":
            logger.info("Jira skeleton rejected for run_id=%s", run_id)
            return ("reject", None)

        # Timeout -> auto-approve
        logger.warning(
            "Jira skeleton approval timeout for run_id=%s — auto-approving",
            run_id,
        )
        return ("approve", None)

    return _callback


def make_slack_jira_review_callback(run_id: str):
    """Create a ``jira_review_callback`` that prompts via Slack.

    Returns a callable: ``(epics_stories_output, run_id) -> bool``
    where ``True`` means proceed to sub-tasks.
    """
    from crewai_productfeature_planner.apis.slack.blocks import jira_review_blocks

    def _callback(
        epics_stories_output: str,
        cb_run_id: str,
    ) -> bool:
        info = get_interactive_run(run_id)
        if not info:
            return True  # auto-proceed

        blocks = jira_review_blocks(run_id, epics_stories_output)
        _post_blocks(
            info["channel"], info["thread_ts"], blocks,
            text="Jira Epics & Stories created — create sub-tasks?",
        )

        decision = _wait_for_decision(run_id, "jira_review")

        if decision == "jira_review_approve":
            logger.info("Jira review approved for run_id=%s", run_id)
            return True

        if decision == "jira_review_skip":
            logger.info("Jira sub-tasks skipped for run_id=%s", run_id)
            return False

        # Timeout -> auto-proceed
        logger.warning(
            "Jira review timeout for run_id=%s — auto-proceeding",
            run_id,
        )
        return True

    return _callback
