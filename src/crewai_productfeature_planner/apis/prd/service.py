"""PRD flow background service — approval callback and flow executor."""

from __future__ import annotations

import os
import threading
from typing import TYPE_CHECKING, Union

from crewai_productfeature_planner.apis.prd.models import (
    ExecutiveSummaryDraft,
    ExecutiveSummaryIteration,
    PRDDraft,
    SECTION_ORDER,
)
from crewai_productfeature_planner.flows._constants import (
    DEFAULT_MIN_SECTION_ITERATIONS,
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
            # Sync pre-PRD pipeline state
            run.finalized_idea = kwargs.get("finalized_idea", run.finalized_idea)
            run.requirements_breakdown = kwargs.get(
                "requirements_breakdown", run.requirements_breakdown,
            )
            exec_summary = kwargs.get("executive_summary")
            if exec_summary is not None:
                run.executive_summary = exec_summary

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


def _sync_flow_state_to_run(run_id: str, flow: "PRDFlow") -> None:
    """Copy final flow state fields onto the in-memory FlowRun.

    Called after ``flow.kickoff()`` returns (or on pause/error) so that
    ``GET /flow/runs/{run_id}`` exposes the full state — matching what
    the CLI has access to.
    """
    run = runs.get(run_id)
    if run is None:
        return

    state = flow.state
    run.current_draft = state.draft
    run.current_section_key = state.current_section_key
    run.iteration = state.iteration
    run.active_agents = list(state.active_agents)
    run.dropped_agents = list(state.dropped_agents)
    run.agent_errors = dict(state.agent_errors)
    run.original_idea = state.original_idea
    run.idea_refined = state.idea_refined
    run.finalized_idea = state.finalized_idea
    run.requirements_breakdown = state.requirements_breakdown
    run.executive_summary = state.executive_summary
    run.confluence_url = state.confluence_url
    run.jira_output = state.jira_output

    # output_file is generated during finalize — extract from state if set
    if state.final_prd and not run.output_file:
        from crewai_productfeature_planner.mongodb import get_output_file
        try:
            output_file = get_output_file(run_id)
            if output_file:
                run.output_file = output_file
        except Exception:
            pass


def run_prd_flow(
    run_id: str,
    idea: str,
    auto_approve: bool = False,
    progress_callback: "Callable[[str, dict], None] | None" = None,
    exec_summary_user_feedback_callback: "Callable | None" = None,
    executive_summary_callback: "Callable | None" = None,
    requirements_approval_callback: "Callable | None" = None,
) -> None:
    """Execute the PRD flow in background and update the run record.

    When *auto_approve* is ``True`` the flow runs end-to-end without
    pausing for manual approval (same as the CLI).  Sections auto-iterate
    and are approved when the critique contains ``SECTION_READY``.

    When *requirements_approval_callback* is provided, the user is
    given a chance to approve or cancel after the requirements breakdown
    — before the executive summary begins.

    When *exec_summary_user_feedback_callback* is provided, the user is
    given a chance to iterate or approve after each executive summary
    iteration — even in auto-approve mode.

    When *executive_summary_callback* is provided, the user is given a
    final review gate between the executive summary and section drafting.
    """
    from crewai_productfeature_planner.flows.prd_flow import (
        PauseRequested, PRDFlow, register_callbacks, cleanup_callbacks,
    )
    from crewai_productfeature_planner.scripts.retry import (
        BillingError, LLMError, ModelBusyError, ShutdownError,
    )

    run = runs[run_id]
    run.status = FlowStatus.RUNNING
    logger.info("[API] PRD flow started (run_id=%s, auto_approve=%s)", run_id, auto_approve)

    # Track job lifecycle in crewJobs
    update_job_started(run_id)

    # Register callbacks in the module-level registry so they survive
    # CrewAI's asyncio.to_thread execution which can lose Flow instance
    # attributes set after __init__.
    register_callbacks(
        run_id,
        progress_callback=progress_callback,
        exec_summary_user_feedback_callback=exec_summary_user_feedback_callback,
        executive_summary_callback=executive_summary_callback,
        requirements_approval_callback=requirements_approval_callback,
    )

    flow: PRDFlow | None = None
    try:
        flow = PRDFlow()
        flow.state.idea = idea
        flow.state.run_id = run_id
        if progress_callback is not None:
            flow.progress_callback = progress_callback
        if exec_summary_user_feedback_callback is not None:
            flow.exec_summary_user_feedback_callback = exec_summary_user_feedback_callback
        if executive_summary_callback is not None:
            flow.executive_summary_callback = executive_summary_callback
        if requirements_approval_callback is not None:
            flow.requirements_approval_callback = requirements_approval_callback
        if not auto_approve:
            flow.approval_callback = make_approval_callback(run_id)

        logger.info(
            "[API] Callbacks set on flow: exec_feedback=%s, exec_completion=%s, "
            "requirements=%s, progress=%s (run_id=%s)",
            flow.exec_summary_user_feedback_callback is not None,
            flow.executive_summary_callback is not None,
            flow.requirements_approval_callback is not None,
            flow.progress_callback is not None,
            run_id,
        )

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
    except ModelBusyError as exc:
        run.status = FlowStatus.PAUSED
        run.error = f"MODEL_BUSY: {exc}"
        update_job_completed(run_id, status="paused")
        logger.warning(
            "[API] PRD flow paused — model busy (run_id=%s): %s. "
            "Will auto-resume on next periodic scan.",
            run_id, exc,
        )
    except ShutdownError as exc:
        run.status = FlowStatus.PAUSED
        run.error = f"SHUTDOWN: {exc}"
        update_job_completed(run_id, status="paused")
        logger.warning(
            "[API] PRD flow paused — server shutting down (run_id=%s): %s. "
            "Will auto-resume on next server start.",
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
    except BaseException as exc:  # noqa: BLE001
        # Catch SystemExit / KeyboardInterrupt so a background thread
        # never takes down the entire server process.
        run.status = FlowStatus.PAUSED
        run.error = f"FATAL_ERROR: {type(exc).__name__}: {exc}"
        try:
            update_job_completed(run_id, status="paused")
        except Exception:  # noqa: BLE001
            pass
        logger.critical(
            "[API] PRD flow caught fatal %s (run_id=%s): %s — "
            "flow paused to prevent server crash",
            type(exc).__name__, run_id, exc,
        )
    finally:
        # Sync flow state to in-memory run for GET /flow/runs/{run_id}
        if flow is not None:
            _sync_flow_state_to_run(run_id, flow)
        # Cleanup approval resources
        approval_events.pop(run_id, None)
        approval_decisions.pop(run_id, None)
        approval_feedback.pop(run_id, None)
        approval_selected.pop(run_id, None)
        pause_requested.pop(run_id, None)
        # Cleanup callback registry
        cleanup_callbacks(run_id)


def restore_prd_state(run_id: str) -> tuple[str, "PRDDraft", "ExecutiveSummaryDraft", str, list[dict], list[dict]]:
    """Rebuild a PRDDraft from MongoDB documents for a given run_id.

    Mirrors the full restore logic in :func:`main._restore_prd_state` so
    that resumed flows have the same state as CLI resumes, including
    executive summary iterations, requirements breakdown, and section
    iteration history.

    Returns:
        A tuple of ``(idea, draft, exec_summary, requirements_breakdown,
        breakdown_history)`` with section content and approval status
        reconstructed from persisted working documents.
    """
    from crewai_productfeature_planner.mongodb import (
        ensure_section_field,
        find_unfinalized,
        get_run_documents,
    )
    from crewai_productfeature_planner.mongodb.working_ideas import (
        find_run_any_status,
    )

    # Look up the idea text — try unfinalized first, then any status
    # (completed runs are valid targets for Jira ticket creation).
    unfinalized = find_unfinalized()
    run_info = next((r for r in unfinalized if r["run_id"] == run_id), None)
    if run_info is None:
        # Fall back to completed / any-status lookup
        doc = find_run_any_status(run_id)
        if doc is None:
            raise ValueError(f"Run {run_id} not found in working ideas")
        run_info = {
            "run_id": doc.get("run_id", run_id),
            "idea": doc.get("idea") or doc.get("finalized_idea") or "",
        }

    idea = run_info["idea"]
    docs = get_run_documents(run_id)

    draft = PRDDraft.create_empty()
    section_keys_set = {key for key, _ in SECTION_ORDER}
    total_iterations = 0

    if docs:
        doc = docs[0]  # single-document model
        section_obj = doc.get("section", {})

        # Edge case: section field missing — reinitialise in MongoDB
        if "section" not in doc:
            logger.warning(
                "Working-idea document for run_id=%s is missing the "
                "'section' field — re-initialising",
                run_id,
            )
            ensure_section_field(run_id)
            section_obj = {}

        # Replay section iteration arrays to reconstruct section state
        if isinstance(section_obj, dict):
            for section_key, iterations in section_obj.items():
                if section_key not in section_keys_set:
                    continue
                section = draft.get_section(section_key)
                if section is None:
                    continue
                if isinstance(iterations, list) and iterations:
                    latest = iterations[-1]
                    if isinstance(latest, dict):
                        content = latest.get("content", "")
                        if content:
                            section.content = content
                        critique = latest.get("critique", "")
                        if critique:
                            section.critique = critique
                        section.iteration = latest.get("iteration", 0)
                        section.updated_date = latest.get("updated_date", "")
                        if section.iteration > total_iterations:
                            total_iterations = section.iteration

    # Infer approval: sections before the last one with content were approved.
    # The last section with content is also marked approved when its
    # critique contains SECTION_READY or its iteration count meets the
    # minimum threshold — indicating the flow had moved past it.
    last_with_content = -1
    for i, section in enumerate(draft.sections):
        if section.content:
            last_with_content = i
    for i, section in enumerate(draft.sections):
        if section.content and i < last_with_content:
            section.is_approved = True
    if last_with_content >= 0:
        last_sec = draft.sections[last_with_content]
        if last_sec.content and not last_sec.is_approved:
            min_iter = int(os.environ.get(
                "PRD_SECTION_MIN_ITERATIONS",
                str(DEFAULT_MIN_SECTION_ITERATIONS),
            ))
            critique_upper = (last_sec.critique or "").upper()
            if "SECTION_READY" in critique_upper or last_sec.iteration >= min_iter:
                last_sec.is_approved = True
                logger.info(
                    "Last section '%s' (index %d) inferred as approved "
                    "(iteration=%d, min=%d, SECTION_READY=%s)",
                    last_sec.title, last_with_content,
                    last_sec.iteration, min_iter,
                    "SECTION_READY" in critique_upper,
                )

    # ── Restore executive_summary iterations ──────────────────
    exec_summary_draft = ExecutiveSummaryDraft()
    if docs:
        doc = docs[0]
        raw_exec = doc.get("executive_summary", [])
        if isinstance(raw_exec, list):
            for entry in raw_exec:
                if not isinstance(entry, dict):
                    continue
                exec_summary_draft.iterations.append(
                    ExecutiveSummaryIteration(
                        content=entry.get("content", ""),
                        iteration=entry.get("iteration", 1),
                        critique=entry.get("critique"),
                        updated_date=entry.get("updated_date", ""),
                    )
                )
            if exec_summary_draft.iterations:
                exec_summary_draft.is_approved = True

    # ── Restore requirements_breakdown ────────────────────────
    requirements_breakdown = ""
    breakdown_history: list[dict] = []
    if docs:
        doc = docs[0]
        raw_reqs = doc.get("requirements_breakdown", [])
        if isinstance(raw_reqs, list) and raw_reqs:
            latest_req = raw_reqs[-1]
            if isinstance(latest_req, dict) and latest_req.get("content"):
                requirements_breakdown = latest_req["content"]
                breakdown_history = [
                    {
                        "iteration": entry.get("iteration", i + 1),
                        "requirements": entry.get("content", ""),
                        "evaluation": entry.get("critique", ""),
                    }
                    for i, entry in enumerate(raw_reqs)
                    if isinstance(entry, dict)
                ]
                logger.info(
                    "Restored requirements_breakdown from %d iteration(s) "
                    "(%d chars)",
                    len(raw_reqs),
                    len(requirements_breakdown),
                )

    # ── Restore refine_idea iterations ─────────────────────────
    refinement_history: list[dict] = []
    if docs:
        doc = docs[0]
        raw_refine = doc.get("refine_idea", [])
        if isinstance(raw_refine, list) and raw_refine:
            refinement_history = [
                {
                    "iteration": entry.get("iteration", i + 1),
                    "idea": entry.get("content", ""),
                    "evaluation": entry.get("critique", ""),
                }
                for i, entry in enumerate(raw_refine)
                if isinstance(entry, dict)
            ]
            logger.info(
                "Restored refine_idea from %d iteration(s)",
                len(raw_refine),
            )

    approved_count = sum(1 for s in draft.sections if s.is_approved)
    exec_iter_count = len(exec_summary_draft.iterations)
    logger.info(
        "Restored PRD state: run_id=%s, %d/%d sections approved, "
        "iteration=%d, exec_summary_iterations=%d, "
        "requirements_breakdown_iterations=%d, "
        "refine_idea_iterations=%d",
        run_id, approved_count, len(draft.sections), total_iterations,
        exec_iter_count, len(breakdown_history), len(refinement_history),
    )

    return idea, draft, exec_summary_draft, requirements_breakdown, breakdown_history, refinement_history


def resume_prd_flow(
    run_id: str,
    auto_approve: bool = False,
    progress_callback: "Callable[[str, dict], None] | None" = None,
    exec_summary_user_feedback_callback: "Callable | None" = None,
    executive_summary_callback: "Callable | None" = None,
    requirements_approval_callback: "Callable | None" = None,
    jira_skeleton_approval_callback: "Callable | None" = None,
    jira_review_callback: "Callable | None" = None,
) -> None:
    """Resume a previously paused/unfinalized PRD flow from MongoDB state.

    When *auto_approve* is ``True`` the flow runs end-to-end without
    pausing for manual approval of individual sections.

    When *requirements_approval_callback* is provided, the user is
    given a chance to approve or cancel after the requirements breakdown
    — before the executive summary begins.

    When *exec_summary_user_feedback_callback* is provided, the user is
    given a chance to iterate or approve after each executive summary
    iteration — even in auto-approve mode.

    When *executive_summary_callback* is provided, the user is given a
    final review gate between the executive summary and section drafting.

    When *jira_skeleton_approval_callback* and *jira_review_callback*
    are provided, the post-completion delivery uses the phased Jira
    approach (skeleton approval → Epics & Stories → Sub-tasks) instead
    of auto-publishing Confluence only.
    """
    from crewai_productfeature_planner.flows.prd_flow import (
        PauseRequested, PRDFlow, register_callbacks, cleanup_callbacks,
    )
    from crewai_productfeature_planner.scripts.retry import (
        BillingError, LLMError, ModelBusyError, ShutdownError,
    )

    run = runs[run_id]
    run.status = FlowStatus.RUNNING
    logger.info("[API] Resuming PRD flow (run_id=%s, auto_approve=%s)", run_id, auto_approve)

    # Reactivate the existing job record.  If no record exists (e.g. the
    # original job was never persisted or was cleaned up), create a fresh
    # one so downstream status updates don't silently fail.
    if not reactivate_job(run_id):
        create_job(job_id=run_id, flow_name="prd", idea=run.original_idea)
    update_job_started(run_id)

    # Register callbacks in the module-level registry
    _cb_kwargs: dict = {
        "progress_callback": progress_callback,
        "exec_summary_user_feedback_callback": exec_summary_user_feedback_callback,
        "executive_summary_callback": executive_summary_callback,
        "requirements_approval_callback": requirements_approval_callback,
    }
    if jira_skeleton_approval_callback is not None:
        _cb_kwargs["jira_skeleton_approval_callback"] = jira_skeleton_approval_callback
    if jira_review_callback is not None:
        _cb_kwargs["jira_review_callback"] = jira_review_callback
    register_callbacks(run_id, **_cb_kwargs)

    flow: PRDFlow | None = None
    try:
        idea, draft, exec_summary, requirements_breakdown, breakdown_history, refinement_history = (
            restore_prd_state(run_id)
        )

        flow = PRDFlow()
        flow.state.run_id = run_id
        flow.state.idea = idea
        flow.state.draft = draft
        flow.state.iteration = max(s.iteration for s in draft.sections)
        flow.state.executive_summary = exec_summary
        flow.state.requirements_breakdown = requirements_breakdown
        flow.state.breakdown_history = breakdown_history
        if requirements_breakdown:
            flow.state.requirements_broken_down = True
        if progress_callback is not None:
            flow.progress_callback = progress_callback
        if exec_summary_user_feedback_callback is not None:
            flow.exec_summary_user_feedback_callback = exec_summary_user_feedback_callback
        if executive_summary_callback is not None:
            flow.executive_summary_callback = executive_summary_callback
        if requirements_approval_callback is not None:
            flow.requirements_approval_callback = requirements_approval_callback
        if jira_skeleton_approval_callback is not None:
            flow.jira_skeleton_approval_callback = jira_skeleton_approval_callback
        if jira_review_callback is not None:
            flow.jira_review_callback = jira_review_callback

        # Set finalized_idea from the last executive summary iteration
        if exec_summary.latest_content:
            flow.state.finalized_idea = exec_summary.latest_content

        # Restore refine_idea state
        if refinement_history:
            flow.state.idea_refined = True
            flow.state.refinement_history = refinement_history
            flow.state.original_idea = idea
            # Use the latest refined idea as the current idea
            latest = refinement_history[-1]
            if latest.get("idea"):
                flow.state.idea = latest["idea"]
        # Fallback: if exec summary has iterations, idea was already refined
        elif exec_summary.iterations:
            flow.state.idea_refined = True

        next_section = draft.next_section()
        if next_section:
            flow.state.current_section_key = next_section.key
            run.current_section_key = next_section.key

        run.current_draft = draft
        run.executive_summary = exec_summary
        run.requirements_breakdown = requirements_breakdown

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
    except ModelBusyError as exc:
        run.status = FlowStatus.PAUSED
        run.error = f"MODEL_BUSY: {exc}"
        update_job_completed(run_id, status="paused")
        logger.warning(
            "[API] Resumed PRD flow paused — model busy (run_id=%s): %s. "
            "Will auto-resume on next periodic scan.",
            run_id, exc,
        )
    except ShutdownError as exc:
        run.status = FlowStatus.PAUSED
        run.error = f"SHUTDOWN: {exc}"
        update_job_completed(run_id, status="paused")
        logger.warning(
            "[API] Resumed PRD flow paused — server shutting down "
            "(run_id=%s): %s. Will auto-resume on next server start.",
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
    except BaseException as exc:  # noqa: BLE001
        # Catch SystemExit / KeyboardInterrupt so a background thread
        # never takes down the entire server process.
        run.status = FlowStatus.PAUSED
        run.error = f"FATAL_ERROR: {type(exc).__name__}: {exc}"
        try:
            update_job_completed(run_id, status="paused")
        except Exception:  # noqa: BLE001
            pass
        logger.critical(
            "[API] Resumed PRD flow caught fatal %s (run_id=%s): %s — "
            "flow paused to prevent server crash",
            type(exc).__name__, run_id, exc,
        )
    finally:
        # Sync flow state to in-memory run for GET /flow/runs/{run_id}
        if flow is not None:
            _sync_flow_state_to_run(run_id, flow)
        approval_events.pop(run_id, None)
        approval_decisions.pop(run_id, None)
        approval_feedback.pop(run_id, None)
        pause_requested.pop(run_id, None)
        # Cleanup callback registry
        cleanup_callbacks(run_id)
