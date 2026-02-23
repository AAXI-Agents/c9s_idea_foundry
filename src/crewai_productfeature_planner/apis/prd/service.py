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
    approval_selected,
    pause_requested,
    runs,
)
from crewai_productfeature_planner.mongodb.crew_jobs import (
    create_job,
    reactivate_job,
    update_job_completed,
    update_job_started,
    update_job_status,
)
from crewai_productfeature_planner.mongodb.working_ideas.repository import mark_completed
from crewai_productfeature_planner.scripts.logging_config import get_logger

if TYPE_CHECKING:
    from crewai_productfeature_planner.flows.prd_flow import PRDFlow

logger = get_logger(__name__)


def make_approval_callback(run_id: str):
    """Create an approval callback function bound to a specific run.

    The callback:
      1. Checks if a pause has been requested (returns ``PAUSE_SENTINEL`` immediately).
      2. Updates the run with the latest agent results and marks ``awaiting_approval``.
      3. Waits on a threading.Event for the user to call the approve/pause endpoint.
      4. Returns ``(selected_agent, True)`` (approve), ``(selected_agent, False)``
         (agent critique), ``(selected_agent, feedback_str)`` (user critique),
         or ``PAUSE_SENTINEL`` to pause.
    """

    def _callback(
        iteration: int,
        section_key: str,
        agent_results: dict[str, str],
        draft: PRDDraft,
        **kwargs,
    ) -> Union[bool, str, tuple[str, Union[bool, str]]]:
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
            # Sync agent tracking from flow state
            run.active_agents = kwargs.get("active_agents", list(agent_results.keys()))
            run.dropped_agents = kwargs.get("dropped_agents", [])
            run.agent_errors = kwargs.get("agent_errors", {})
            run.original_idea = kwargs.get("original_idea", "")
            run.idea_refined = kwargs.get("idea_refined", False)

        update_job_status(run_id, "awaiting_approval")

        logger.info(
            "[API] Awaiting user approval (run_id=%s, section=%s, iteration=%d, agents=%s)",
            run_id, section_key, iteration, list(agent_results.keys()),
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
        selected = approval_selected.pop(run_id, "")

        if run is not None:
            run.status = FlowStatus.RUNNING

        update_job_status(run_id, "running")

        # Determine the agent to use (fallback to first available)
        default_agent = next(iter(agent_results)) if agent_results else ""
        agent_name = selected or default_agent

        # If user provided critique feedback, return it as a tuple
        if not approved and fb:
            logger.info(
                "[API] User provided critique feedback for run_id=%s section=%s agent=%s (%d chars)",
                run_id, section_key, agent_name, len(fb),
            )
            return (agent_name, fb)

        logger.info(
            "[API] User decision for run_id=%s section=%s agent=%s: %s",
            run_id, section_key, agent_name,
            "APPROVED" if approved else "CONTINUE",
        )
        return (agent_name, approved)

    return _callback


def run_prd_flow(run_id: str, idea: str, auto_approve: bool = False) -> None:
    """Execute the PRD flow in background and update the run record.

    When *auto_approve* is ``True`` the flow runs end-to-end without
    pausing for manual approval (same as the CLI).  Sections auto-iterate
    and are approved when the critique contains ``SECTION_READY``.
    """
    from crewai_productfeature_planner.flows.prd_flow import PauseRequested, PRDFlow
    from crewai_productfeature_planner.scripts.retry import BillingError, LLMError

    run = runs[run_id]
    run.status = FlowStatus.RUNNING
    logger.info("[API] PRD flow started (run_id=%s, auto_approve=%s)", run_id, auto_approve)

    # Track job lifecycle in crewJobs
    update_job_started(run_id)

    try:
        flow = PRDFlow()
        flow.state.idea = idea
        flow.state.run_id = run_id
        if not auto_approve:
            flow.approval_callback = make_approval_callback(run_id)
        result = flow.kickoff()
        run.result = result
        run.status = FlowStatus.COMPLETED

        # Safety net: if finalize() failed or was skipped, persist now
        if not flow.state.is_ready:
            logger.warning(
                "[API] finalize() incomplete for run_id=%s — "
                "persisting finalized PRD from service",
                run_id,
            )
            mark_completed(run_id)

        update_job_completed(run_id, status="completed")
        logger.info("[API] PRD flow completed (run_id=%s)", run_id)
    except PauseRequested:
        run.status = FlowStatus.PAUSED
        update_job_completed(run_id, status="paused")
        logger.info("[API] PRD flow paused by user (run_id=%s)", run_id)
    except BillingError as exc:
        run.status = FlowStatus.PAUSED
        run.error = f"BILLING_ERROR: {exc}"
        update_job_completed(run_id, status="paused")
        logger.error(
            "[API] PRD flow paused due to billing error (run_id=%s): %s",
            run_id, exc,
        )
    except LLMError as exc:
        run.status = FlowStatus.PAUSED
        run.error = f"LLM_ERROR: {exc}"
        update_job_completed(run_id, status="paused")
        logger.error(
            "[API] PRD flow paused due to LLM error (run_id=%s): %s",
            run_id, exc,
        )
    except Exception as exc:
        run.status = FlowStatus.PAUSED
        run.error = f"INTERNAL_ERROR: {exc}"
        update_job_completed(run_id, status="paused")
        logger.error("[API] PRD flow failed (kept inprogress, run_id=%s): %s", run_id, exc)
    finally:
        # Cleanup approval resources
        approval_events.pop(run_id, None)
        approval_decisions.pop(run_id, None)
        approval_feedback.pop(run_id, None)
        approval_selected.pop(run_id, None)
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
        draft_obj = doc.get("draft", {})
        critique = doc.get("critique", "")

        # Extract section content from the draft dict
        if isinstance(draft_obj, dict):
            content = draft_obj.get(section_key, "")
        else:
            # Backward-compat: legacy docs stored draft as a plain string
            content = draft_obj or ""

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


def resume_prd_flow(run_id: str, auto_approve: bool = False) -> None:
    """Resume a previously paused/unfinalized PRD flow from MongoDB state.

    When *auto_approve* is ``True`` the flow runs end-to-end without
    pausing for manual approval.
    """
    from crewai_productfeature_planner.flows.prd_flow import PauseRequested, PRDFlow
    from crewai_productfeature_planner.scripts.retry import BillingError, LLMError

    run = runs[run_id]
    run.status = FlowStatus.RUNNING
    logger.info("[API] Resuming PRD flow (run_id=%s, auto_approve=%s)", run_id, auto_approve)

    # Reactivate the existing job record (don't create a duplicate)
    reactivate_job(run_id)
    update_job_started(run_id)

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
            run.current_section_key = next_section.key

        run.current_draft = draft
        if not auto_approve:
            flow.approval_callback = make_approval_callback(run_id)
        result = flow.kickoff()
        run.result = result
        run.status = FlowStatus.COMPLETED

        # Safety net: if finalize() failed or was skipped, persist now
        if not flow.state.is_ready:
            logger.warning(
                "[API] finalize() incomplete for resumed run_id=%s — "
                "persisting finalized PRD from service",
                run_id,
            )
            mark_completed(run_id)

        update_job_completed(run_id, status="completed")
        logger.info("[API] Resumed PRD flow completed (run_id=%s)", run_id)
    except PauseRequested:
        run.status = FlowStatus.PAUSED
        update_job_completed(run_id, status="paused")
        logger.info("[API] Resumed PRD flow paused again (run_id=%s)", run_id)
    except BillingError as exc:
        run.status = FlowStatus.PAUSED
        run.error = f"BILLING_ERROR: {exc}"
        update_job_completed(run_id, status="paused")
        logger.error(
            "[API] Resumed PRD flow paused due to billing error (run_id=%s): %s",
            run_id, exc,
        )
    except LLMError as exc:
        run.status = FlowStatus.PAUSED
        run.error = f"LLM_ERROR: {exc}"
        update_job_completed(run_id, status="paused")
        logger.error(
            "[API] Resumed PRD flow paused due to LLM error (run_id=%s): %s",
            run_id, exc,
        )
    except Exception as exc:
        run.status = FlowStatus.PAUSED
        run.error = f"INTERNAL_ERROR: {exc}"
        update_job_completed(run_id, status="paused")
        logger.error("[API] Resumed PRD flow failed (kept inprogress, run_id=%s): %s", run_id, exc)
    finally:
        approval_events.pop(run_id, None)
        approval_decisions.pop(run_id, None)
        approval_feedback.pop(run_id, None)
        pause_requested.pop(run_id, None)
