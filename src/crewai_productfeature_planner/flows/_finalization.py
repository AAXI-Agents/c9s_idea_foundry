"""Finalization and post-completion logic for the PRD flow.

Handles save_progress, finalize, Confluence publish, and phased Jira
ticketing.  Extracted from ``prd_flow.py`` for modularity.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from crewai_productfeature_planner.mongodb import (
    get_output_file,
    mark_completed,
    mark_paused,
    save_output_file,
)
from crewai_productfeature_planner.scripts.confluence_xhtml import md_to_confluence_xhtml
from crewai_productfeature_planner.scripts.logging_config import get_logger
from crewai_productfeature_planner.tools.file_write_tool import PRDFileWriteTool

if TYPE_CHECKING:
    from crewai_productfeature_planner.flows.prd_flow import PRDFlow

logger = get_logger(__name__)


def save_progress(flow: PRDFlow) -> str:
    """Write a progress markdown capturing whatever work is available.

    Called when the flow is interrupted (error, pause, billing) so
    the user still gets a file in ``output/prds/`` with the refined
    idea, requirements breakdown, and any completed sections.

    Returns:
        The save-result string from :class:`PRDFileWriteTool`, or an
        empty string if there is nothing meaningful to save.
    """
    parts: list[str] = []

    # Refined idea
    idea_text = flow.state.finalized_idea or flow.state.idea
    if idea_text:
        parts.append(f"## Refined Idea\n\n{idea_text}")

    # Requirements breakdown
    if flow.state.requirements_broken_down and flow.state.requirements_breakdown:
        parts.append(f"## Requirements Breakdown\n\n{flow.state.requirements_breakdown}")

    # Executive summary (latest iteration)
    if flow.state.executive_summary.latest_content:
        parts.append(f"## Executive Summary\n\n{flow.state.executive_summary.latest_content}")

    # Any drafted sections (skip executive_summary — already above)
    for section in flow.state.draft.sections:
        if section.content and section.key != "executive_summary":
            parts.append(f"## {section.title}\n\n{section.content}")

    if not parts:
        logger.info("[Progress] Nothing to save — no content produced yet")
        return ""

    # Use the definitive header when every section is approved;
    # otherwise mark the document as in-progress.
    all_approved = flow.state.draft.all_approved()
    header = (
        "# Product Requirements Document\n\n"
        if all_approved
        else "# Product Requirements Document (In Progress)\n\n"
    )
    content = header + "\n\n---\n\n".join(parts)

    writer = PRDFileWriteTool(output_dir="output/prds/_drafts")
    save_result = writer._run(
        content=content,
        filename="",
        version=max(flow.state.iteration, 1),
    )
    logger.info("[Progress] %s", save_result)

    # Persist the output file path to the workingIdeas document
    persist_output_path(flow, save_result)

    # Update workingIdeas status from "failed" → "paused" so a
    # subsequent restart treats this as a resumable run.
    mark_paused(flow.state.run_id)

    return save_result


def persist_output_path(flow: PRDFlow, save_result: str) -> None:
    """Extract the file path from *save_result* and store it in MongoDB.

    Before storing the new path, any previously stored output file
    for this run is deleted from disk so only the latest version
    remains.

    The *save_result* string is of the form
    ``"PRD saved to output/prds/2026/02/prd_v10_20260223_071542.md"``.
    """
    from pathlib import Path

    # Extract path from "PRD saved to <path>"
    prefix = "PRD saved to "
    if save_result.startswith(prefix):
        output_path = save_result[len(prefix):]
    else:
        output_path = save_result

    # Delete the previous output file (if any) so only the latest
    # version exists on disk.
    old_path = get_output_file(flow.state.run_id)
    if old_path and old_path != output_path:
        try:
            p = Path(old_path)
            if p.is_file():
                p.unlink()
                logger.info(
                    "[Cleanup] Deleted previous output file: %s", old_path,
                )
        except OSError as exc:
            logger.warning(
                "[Cleanup] Could not delete previous output %s: %s",
                old_path, exc,
            )

    save_output_file(flow.state.run_id, output_path)


def finalize(flow: PRDFlow) -> str:
    """Assemble the final PRD from all approved sections and persist."""
    logger.info("[Step 4] Finalising PRD (total iterations=%d)", flow.state.iteration)
    flow.state.final_prd = flow.state.draft.assemble()

    # Save Markdown to file
    writer = PRDFileWriteTool()
    save_result = writer._run(
        content=flow.state.final_prd,
        filename="",
        version=flow.state.iteration,
    )

    # Persist the output file path to the workingIdeas document
    persist_output_path(flow, save_result)

    # Convert to Confluence-compatible XHTML
    confluence_xhtml = md_to_confluence_xhtml(flow.state.final_prd)
    logger.info(
        "[Step 4] Generated Confluence XHTML (%d chars)", len(confluence_xhtml)
    )

    # Mark working-idea document as completed
    mark_completed(flow.state.run_id)

    flow.state.is_ready = True
    flow.state.status = "completed"
    flow.state.completed_at = datetime.now(timezone.utc).isoformat()
    flow.state.update_date = flow.state.completed_at
    logger.info("[Step 4] %s", save_result)

    flow._notify_progress("prd_complete", {
        "total_iterations": flow.state.iteration,
    })

    # ── Post-completion: Confluence publish & Jira ticketing ──
    run_post_completion(flow)

    return save_result


# ------------------------------------------------------------------
# Post-completion pipeline (Confluence + Jira)
# ------------------------------------------------------------------

def run_post_completion(flow: PRDFlow) -> None:
    """Run the Atlassian delivery crew after PRD finalization.

    When Jira skeleton/review callbacks are set (interactive mode),
    uses the phased Jira approach:
    1. Confluence publish via crew
    2. Phase 1: Generate skeleton → user approval
    3. Phase 2: Create Epics & Stories → user review
    4. Phase 3: Create sub-tasks

    Otherwise falls back to the single post-completion crew for
    backward compatibility (auto-approve mode).

    Failures are logged but do not fail the overall flow.
    """
    try:
        jira_skel_cb = flow._resolve_callback("jira_skeleton_approval_callback")
        if jira_skel_cb is not None:
            _run_phased_post_completion(flow)
        else:
            _run_auto_post_completion(flow)
    except Exception as exc:
        logger.warning(
            "[PostCompletion] Atlassian delivery failed — "
            "PRD is saved but not published: %s",
            exc,
        )


def _run_auto_post_completion(flow: PRDFlow) -> None:
    """Run Confluence-only post-completion crew (auto-approve mode).

    Jira ticketing is **never** included in auto-approve mode because
    it must go through the phased approval flow (skeleton → Epics &
    Stories → Sub-tasks) with user interaction at each gate.
    """
    from crewai_productfeature_planner.orchestrator import (
        build_post_completion_crew,
    )
    from crewai_productfeature_planner.scripts.retry import (
        crew_kickoff_with_retry,
    )

    crew = build_post_completion_crew(flow, confluence_only=True)
    if crew is None:
        logger.info(
            "[PostCompletion] No delivery steps needed — skipping."
        )
        return
    result = crew_kickoff_with_retry(crew, step_label="post_completion")
    persist_post_completion(flow, result)


def _run_phased_post_completion(flow: PRDFlow) -> None:
    """Run phased Confluence + Jira delivery with approval gates."""
    from crewai_productfeature_planner.orchestrator import (
        build_post_completion_crew,
    )
    from crewai_productfeature_planner.orchestrator._jira import (
        _check_jira_prerequisites,
        _persist_jira_phase,
        build_jira_epics_stories_stage,
        build_jira_skeleton_stage,
        build_jira_subtasks_stage,
    )
    from crewai_productfeature_planner.scripts.retry import (
        crew_kickoff_with_retry,
    )

    # ── Step 1: Confluence publish (reuse crew minus Jira tasks) ──
    # Build post-completion crew — it still handles Confluence.
    # We run it first; Jira is handled separately below.
    # Temporarily clear jira credentials so the crew only does Confluence.
    from crewai_productfeature_planner.orchestrator._helpers import (
        _has_confluence_credentials,
        _has_gemini_credentials,
    )

    confluence_done = bool(getattr(flow.state, "confluence_url", ""))
    has_confluence = _has_confluence_credentials() and _has_gemini_credentials()
    if has_confluence and not confluence_done and flow.state.final_prd:
        crew = build_post_completion_crew(flow, confluence_only=True)
        if crew is not None:
            result = crew_kickoff_with_retry(
                crew, step_label="post_completion_confluence",
            )
            persist_post_completion(flow, result)

    # ── Phase 1: Generate Jira skeleton ───────────────────────
    skip_reason = _check_jira_prerequisites(flow)
    if skip_reason:
        logger.info("[PhasedJira] Skipping Jira — %s", skip_reason)
        return

    flow._notify_progress("jira_skeleton_start", {})

    skeleton_stage = build_jira_skeleton_stage(flow)
    if not skeleton_stage.should_skip():
        result = skeleton_stage.run()
        skeleton_stage.apply(result)

        flow._notify_progress("jira_skeleton_ready", {
            "skeleton": flow.state.jira_skeleton[:500],
        })

        # Ask user for approval
        jira_skel_cb = flow._resolve_callback("jira_skeleton_approval_callback")
        assert jira_skel_cb is not None
        try:
            action, edited = jira_skel_cb(
                flow.state.jira_skeleton, flow.state.run_id,
            )
        except Exception:
            logger.warning(
                "[PhasedJira] Skeleton approval callback failed",
                exc_info=True,
            )
            return

        if action == "reject":
            logger.info("[PhasedJira] User rejected skeleton — skipping Jira")
            flow.state.jira_phase = ""
            _persist_jira_phase(flow.state.run_id, "")
            return

        # Apply edits if provided
        if edited:
            flow.state.jira_skeleton = edited
        flow.state.jira_phase = "skeleton_approved"
        _persist_jira_phase(flow.state.run_id, "skeleton_approved")
        logger.info("[PhasedJira] Skeleton approved — proceeding to Phase 2")

    # ── Phase 2: Create Epics & Stories ───────────────────────
    flow._notify_progress("jira_epics_stories_start", {})

    es_stage = build_jira_epics_stories_stage(flow)
    if not es_stage.should_skip():
        result = es_stage.run()
        es_stage.apply(result)

        flow._notify_progress("jira_epics_stories_complete", {
            "output_preview": flow.state.jira_epics_stories_output[:500],
        })

        # Ask user to review before sub-tasks
        jira_rev_cb = flow._resolve_callback("jira_review_callback")
        if jira_rev_cb is not None:
            try:
                proceed = jira_rev_cb(
                    flow.state.jira_epics_stories_output,
                    flow.state.run_id,
                )
            except Exception:
                logger.warning(
                    "[PhasedJira] Review callback failed", exc_info=True,
                )
                proceed = True  # Default to proceeding

            if not proceed:
                logger.info(
                    "[PhasedJira] User declined sub-task creation — "
                    "Epics/Stories created but no sub-tasks"
                )
                return
        flow.state.jira_phase = "subtasks_ready"
        _persist_jira_phase(flow.state.run_id, "subtasks_ready")

    # ── Phase 3: Create Sub-tasks ─────────────────────────────
    flow._notify_progress("jira_subtasks_start", {})

    subtasks_stage = build_jira_subtasks_stage(flow)
    if not subtasks_stage.should_skip():
        result = subtasks_stage.run()
        subtasks_stage.apply(result)

        flow._notify_progress("jira_published", {
            "ticket_count": len(
                __import__("re").findall(
                    r"[A-Z]{2,10}-\d+",
                    flow.state.jira_output or "",
                ),
            ),
        })

    # ── Mark Jira delivery complete in productRequirements ────
    if flow.state.jira_phase == "subtasks_done":
        try:
            from crewai_productfeature_planner.mongodb.product_requirements import (
                get_jira_tickets,
                upsert_delivery_record,
            )
            tickets = get_jira_tickets(flow.state.run_id)
            upsert_delivery_record(
                flow.state.run_id,
                jira_completed=True,
                jira_output=flow.state.jira_output or "",
            )
            logger.info(
                "[PhasedJira] Marked jira_completed=True for run_id=%s "
                "(%d tickets persisted)",
                flow.state.run_id, len(tickets),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[PhasedJira] Failed to mark jira_completed: %s", exc,
            )


# ------------------------------------------------------------------
# Post-completion output persistence
# ------------------------------------------------------------------

def persist_post_completion(flow: PRDFlow, result: object) -> None:
    """Parse crew *result* and update the delivery record.

    Detects Confluence publish and Jira ticket creation from the
    raw crew output, then upserts the ``productRequirements``
    record so the startup orchestrator knows what has already been
    delivered.
    """
    import re as _re

    try:
        raw_output = result.raw if hasattr(result, "raw") else str(result)
    except Exception:  # noqa: BLE001
        return

    try:
        from crewai_productfeature_planner.mongodb.product_requirements import (
            upsert_delivery_record,
        )

        # Detect Confluence publish
        conf_url = extract_confluence_url(raw_output) or getattr(
            flow.state, "confluence_url", "",
        )
        conf_done = bool(conf_url)

        # NOTE: Jira completion is NOT detected here.  The jira_phase
        # field and jira_completed flag are managed exclusively by the
        # interactive phased Jira flow (orchestrator/_jira.py).
        # Detecting Jira keywords in crew output caused false positives
        # (e.g. Jira issue keys mentioned in PRD content) and set
        # jira_phase='subtasks_done' without user approval — violating
        # the Jira approval gate invariant (v0.15.8).

        upsert_delivery_record(
            flow.state.run_id,
            confluence_published=conf_done,
            confluence_url=conf_url,
        )
        logger.info(
            "[PostCompletion] Delivery record updated for "
            "run_id=%s (confluence=%s)",
            flow.state.run_id,
            "done" if conf_done else "pending",
        )

        # ── Progress heartbeat for Confluence ─────────────
        if conf_done:
            flow._notify_progress("confluence_published", {
                "url": conf_url,
            })
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[PostCompletion] Failed to persist delivery record: %s",
            exc,
        )


# ------------------------------------------------------------------
# Output detection helpers
# ------------------------------------------------------------------

def extract_confluence_url(output: str) -> str:
    """Extract a Confluence URL from crew output text."""
    import re
    match = re.search(r"https?://[^\s]+atlassian[^\s]*wiki[^\s]*", output)
    if match:
        return match.group(0).rstrip(".,;:()\"\'")
    match = re.search(r"https?://[^\s]+/wiki/[^\s]*", output)
    if match:
        return match.group(0).rstrip(".,;:()\"\'")
    return ""


def jira_detected_in_output(output: str) -> bool:
    """Detect Jira ticket creation in crew output."""
    import re
    lower = output.lower()
    if "fail" in lower[:200]:
        return False
    has_keyword = any(kw in lower for kw in [
        "epic", "story", "stories", "issue_key", "issue key",
    ])
    has_issue_key = bool(re.search(r"[A-Z]{2,10}-\d+", output))
    return has_keyword and has_issue_key


__all__ = [
    "save_progress",
    "persist_output_path",
    "finalize",
    "run_post_completion",
    "persist_post_completion",
    "extract_confluence_url",
    "jira_detected_in_output",
]
