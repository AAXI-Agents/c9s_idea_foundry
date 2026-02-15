"""PRD flow background service — approval callback and flow executor."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Union

from crewai_productfeature_planner.apis.prd.models import (
    PRDDraft,
    SECTION_ORDER,
)
from crewai_productfeature_planner.apis.shared import (
    FlowStatus,
    approval_decisions,
    approval_events,
    approval_feedback,
    pause_requested,
    runs,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

if TYPE_CHECKING:
    from crewai_productfeature_planner.flows.prd_flow import PRDFlow

logger = get_logger(__name__)


def make_approval_callback(run_id: str):
    """Create an approval callback function bound to a specific run.

    The callback:
      1. Checks if a pause has been requested (returns ``PAUSE_SENTINEL`` immediately).
      2. Updates the run with the latest section draft and marks ``awaiting_approval``.
      3. Waits on a threading.Event for the user to call the approve/pause endpoint.
      4. Returns ``True`` (approve section), ``False`` (agent critique), a ``str``
         (user-provided critique feedback), or ``PAUSE_SENTINEL`` to pause.
    """

    def _callback(iteration: int, section_key: str, section_content: str, draft: PRDDraft) -> Union[bool, str]:
        from crewai_productfeature_planner.flows.prd_flow import PAUSE_SENTINEL

        # Check if pause was requested while the flow was running
        if pause_requested.pop(run_id, False):
            logger.info("[API] Pause flag detected for run_id=%s, pausing", run_id)
            return PAUSE_SENTINEL

        run = runs.get(run_id)
        if run is not None:
            run.iteration = iteration
            run.current_draft = draft
            run.current_section_key = section_key
            run.status = FlowStatus.AWAITING_APPROVAL

        logger.info(
            "[API] Awaiting user approval (run_id=%s, section=%s, iteration=%d)",
            run_id, section_key, iteration,
        )

        event = approval_events.setdefault(run_id, threading.Event())
        event.clear()
        event.wait()  # blocks until user hits /flow/prd/approve or /flow/prd/pause

        # Check if pause was requested while awaiting approval
        if pause_requested.pop(run_id, False):
            logger.info("[API] Pause requested during approval for run_id=%s", run_id)
            return PAUSE_SENTINEL

        approved = approval_decisions.pop(run_id, False)
        fb = approval_feedback.pop(run_id, "")

        if run is not None:
            run.status = FlowStatus.RUNNING

        # If user provided critique feedback, return it as a string
        if not approved and fb:
            logger.info(
                "[API] User provided critique feedback for run_id=%s section=%s (%d chars)",
                run_id, section_key, len(fb),
            )
            return fb

        logger.info(
            "[API] User decision for run_id=%s section=%s: %s",
            run_id, section_key,
            "APPROVED" if approved else "CONTINUE",
        )
        return approved

    return _callback


def run_prd_flow(run_id: str, idea: str) -> None:
    """Execute the PRD flow in background and update the run record."""
    from crewai_productfeature_planner.flows.prd_flow import PauseRequested, PRDFlow

    run = runs[run_id]
    run.status = FlowStatus.RUNNING
    logger.info("[API] PRD flow started (run_id=%s)", run_id)

    try:
        flow = PRDFlow()
        flow.state.idea = idea
        flow.state.run_id = run_id
        flow.approval_callback = make_approval_callback(run_id)
        result = flow.kickoff()
        run.result = result
        run.status = FlowStatus.COMPLETED
        logger.info("[API] PRD flow completed (run_id=%s)", run_id)
    except PauseRequested:
        run.status = FlowStatus.PAUSED
        logger.info("[API] PRD flow paused by user (run_id=%s)", run_id)
    except Exception as exc:
        run.status = FlowStatus.FAILED
        run.error = str(exc)
        logger.error("[API] PRD flow failed (run_id=%s): %s", run_id, exc)
    finally:
        # Cleanup approval resources
        approval_events.pop(run_id, None)
        approval_decisions.pop(run_id, None)
        approval_feedback.pop(run_id, None)
        pause_requested.pop(run_id, None)


def restore_prd_state(run_id: str) -> tuple[str, "PRDDraft"]:
    """Rebuild a PRDDraft from MongoDB documents for a given run_id.

    Returns:
        A tuple of ``(idea, draft)`` with section content and approval status
        reconstructed from persisted working documents.
    """
    from crewai_productfeature_planner.mongodb import (
        find_unfinalized,
        get_run_documents,
    )

    # Look up the idea text from unfinalized runs
    unfinalized = find_unfinalized()
    run_info = next((r for r in unfinalized if r["run_id"] == run_id), None)
    if run_info is None:
        raise ValueError(f"Run {run_id} not found in unfinalized working ideas")

    idea = run_info["idea"]
    docs = get_run_documents(run_id)

    draft = PRDDraft.create_empty()
    section_keys_set = {key for key, _ in SECTION_ORDER}

    for doc in docs:
        section_key = doc.get("section_key", "")
        content = doc.get("draft", "")
        critique = doc.get("critique", "")

        if section_key and section_key in section_keys_set:
            section = draft.get_section(section_key)
            if section is None:
                continue
            if content:
                section.content = content
            if critique:
                section.critique = critique
            section.iteration = max(section.iteration, doc.get("iteration", 0))

    # Infer approval: sections before the last one with content were approved
    last_with_content = -1
    for i, section in enumerate(draft.sections):
        if section.content:
            last_with_content = i
    for i, section in enumerate(draft.sections):
        if section.content and i < last_with_content:
            section.is_approved = True

    return idea, draft


def resume_prd_flow(run_id: str) -> None:
    """Resume a previously paused/unfinalized PRD flow from MongoDB state."""
    from crewai_productfeature_planner.flows.prd_flow import PauseRequested, PRDFlow

    run = runs[run_id]
    run.status = FlowStatus.RUNNING
    logger.info("[API] Resuming PRD flow (run_id=%s)", run_id)

    try:
        idea, draft = restore_prd_state(run_id)

        flow = PRDFlow()
        flow.state.run_id = run_id
        flow.state.idea = idea
        flow.state.draft = draft
        flow.state.iteration = max(s.iteration for s in draft.sections)

        next_section = draft.next_section()
        if next_section:
            flow.state.current_section_key = next_section.key

        run.current_draft = draft
        flow.approval_callback = make_approval_callback(run_id)
        result = flow.kickoff()
        run.result = result
        run.status = FlowStatus.COMPLETED
        logger.info("[API] Resumed PRD flow completed (run_id=%s)", run_id)
    except PauseRequested:
        run.status = FlowStatus.PAUSED
        logger.info("[API] Resumed PRD flow paused again (run_id=%s)", run_id)
    except Exception as exc:
        run.status = FlowStatus.FAILED
        run.error = str(exc)
        logger.error("[API] Resumed PRD flow failed (run_id=%s): %s", run_id, exc)
    finally:
        approval_events.pop(run_id, None)
        approval_decisions.pop(run_id, None)
        approval_feedback.pop(run_id, None)
        pause_requested.pop(run_id, None)
