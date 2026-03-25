"""Executive summary iteration logic for the PRD flow.

Handles the Phase 1 executive summary drafting, critique loops, and
user feedback gates.  Extracted from ``prd_flow.py`` for modularity.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from crewai import Agent, Crew, Process, Task

from crewai_productfeature_planner.apis.prd.models import (
    ExecutiveSummaryIteration,
    get_default_agent,
)
from crewai_productfeature_planner.components.document import sanitize_section_content
from crewai_productfeature_planner.flows._constants import (
    _get_section_iteration_limits,
)
from crewai_productfeature_planner.mongodb import (
    save_executive_summary,
    save_failed,
    save_finalized_idea,
    update_executive_summary_critique,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger, is_verbose
from crewai_productfeature_planner.scripts.retry import (
    BillingError,
    ModelBusyError,
    crew_kickoff_with_retry,
)

if TYPE_CHECKING:
    from crewai_productfeature_planner.flows.prd_flow import PRDFlow

logger = get_logger(__name__)


def exec_summary_user_gate(
    flow: PRDFlow,
    content: str,
    iteration: int,
) -> str | None | bool:
    """Prompt the user for feedback after an exec summary iteration.

    Returns:
        ``False``  — the user approved; caller should stop iterating
                     and return immediately.
        ``None``   — no feedback; continue normally with AI critique.
        ``str``    — user-provided feedback text to inject into the
                     next refine step.
    """
    assert flow.exec_summary_user_feedback_callback is not None or \
        flow._resolve_callback("exec_summary_user_feedback_callback") is not None
    cb = flow._resolve_callback("exec_summary_user_feedback_callback")
    try:
        action, feedback_text = cb(
            content,
            flow.state.idea,
            flow.state.run_id,
            iteration,
        )
    except Exception:  # noqa: BLE001
        logger.debug(
            "exec_summary_user_feedback_callback failed at "
            "iteration %d",
            iteration,
            exc_info=True,
        )
        return None

    if action == "approve":
        logger.info(
            "[ExecSummary] User approved at iteration %d",
            iteration,
        )
        flow.state.executive_summary.is_approved = True
        # Persist final state
        flow.state.finalized_idea = (
            flow.state.executive_summary.latest_content
        )
        save_finalized_idea(
            run_id=flow.state.run_id,
            finalized_idea=flow.state.finalized_idea,
        )
        logger.info(
            "[ExecSummary] Copied executive summary to "
            "finalized_idea (%d chars)",
            len(flow.state.finalized_idea),
        )
        flow._notify_progress("executive_summary_complete", {
            "iterations": len(
                flow.state.executive_summary.iterations,
            ),
            "chars": len(flow.state.finalized_idea),
        })
        return False

    if action == "feedback" and feedback_text:
        logger.info(
            "[ExecSummary] User feedback at iteration %d (%d chars)",
            iteration, len(feedback_text),
        )
        return feedback_text

    # "skip" or unknown — proceed without feedback
    return None


def iterate_executive_summary(
    flow: PRDFlow,
    agents: dict[str, Agent],
    task_configs: dict,
    *,
    critic_agent: Agent | None = None,
) -> None:
    """Draft and iterate the executive summary using critique_prd_task.

    Uses ``draft_prd_task`` for the initial draft, then loops
    ``critique_prd_task`` up to min/max iterations.  Each iteration
    both critiques the current summary and produces a refined version.

    When a dedicated *critic_agent* is supplied, it handles all
    critique tasks — using a lightweight (flash) model with no tools
    for faster evaluation.  Otherwise, falls back to cross-agent
    collaboration or self-critique.

    The executive summary is stored at the top-level
    ``executive_summary`` array in ``workingIdeas`` (not under ``draft``).
    """
    min_iter, max_iter = _get_section_iteration_limits()
    # Pick the default agent for the executive summary phase
    default_name = get_default_agent()
    pm = agents.get(default_name) or next(iter(agents.values()))

    # Pick a critic agent.  Priority:
    #   1) Dedicated lightweight critic (fast model, no tools)
    #   2) Secondary PM agent (cross-agent collaboration)
    #   3) Same PM agent (self-critique)
    if critic_agent is not None:
        critic = critic_agent
        critic_name = "critic"
        logger.info(
            "[ExecSummary] Using dedicated lightweight critic agent",
        )
    else:
        critic = pm
        critic_name = default_name
        for name, agent_obj in agents.items():
            if name != default_name:
                critic = agent_obj
                critic_name = name
                logger.info(
                    "[ExecSummary] Cross-agent collaboration: "
                    "'%s' will critique '%s' drafts",
                    critic_name, default_name,
                )
                break

    # Always persist the original user-inputted idea, not the refined one
    user_idea = flow.state.original_idea or flow.state.idea

    flow._notify_progress("section_start", {
        "section_title": "Executive Summary",
        "section_key": "executive_summary",
        "section_step": 1,
        "total_sections": len(flow.state.draft.sections),
    })

    # ── Pre-draft user feedback (optional) ────────────────
    initial_guidance: str | None = None
    user_fb_cb = flow._resolve_callback("exec_summary_user_feedback_callback")
    if user_fb_cb is not None:
        try:
            action, feedback_text = user_fb_cb(
                "",              # no content yet
                flow.state.idea,
                flow.state.run_id,
                0,               # iteration 0 = pre-draft
            )
            if action == "feedback" and feedback_text:
                initial_guidance = feedback_text
                logger.info(
                    "[ExecSummary] User provided initial guidance "
                    "(%d chars)",
                    len(initial_guidance),
                )
            else:
                logger.info(
                    "[ExecSummary] User skipped initial guidance",
                )
        except Exception:  # noqa: BLE001
            logger.debug(
                "exec_summary_user_feedback_callback failed at "
                "pre-draft",
                exc_info=True,
            )

    # ── Initial draft (iteration 1) ───────────────────────
    draft_description = task_configs["draft_prd_task"]["description"].format(
        idea=flow.state.idea,
        executive_summary="(initial draft — first iteration)",
    )
    if initial_guidance:
        draft_description += (
            "\n\n--- USER GUIDANCE ---\n"
            f"{initial_guidance}\n"
            "--- END OF USER GUIDANCE ---\n\n"
            "Incorporate the user's guidance above into your draft."
        )
    draft_task = Task(
        description=draft_description,
        expected_output=task_configs["draft_prd_task"]["expected_output"],
        agent=pm,
    )
    crew = Crew(
        agents=[pm],
        tasks=[draft_task],
        process=Process.sequential,
        verbose=is_verbose(),
    )
    try:
        draft_result = crew_kickoff_with_retry(
            crew, step_label="draft_executive_summary",
        )
    except Exception as exc:
        logger.error("[ExecSummary] Initial draft failed: %s", exc)
        save_failed(
            run_id=flow.state.run_id,
            idea=user_idea,
            iteration=0,
            error=str(exc),
            step="draft_executive_summary",
        )
        raise

    current_content = draft_result.raw

    # Guard: strip JSON document dumps the LLM may produce
    current_content = sanitize_section_content(
        current_content, "executive_summary",
    )

    now = datetime.now(timezone.utc).isoformat()
    first_iter = ExecutiveSummaryIteration(
        content=current_content,
        iteration=1,
        critique=None,
        updated_date=now,
    )
    flow.state.executive_summary.iterations.append(first_iter)
    flow.state.iteration = 1
    flow.state.update_date = now

    save_executive_summary(
        run_id=flow.state.run_id,
        idea=user_idea,
        iteration=1,
        content=current_content,
        critique=None,
    )
    logger.info(
        "[ExecSummary] Initial draft (%d chars)", len(current_content),
    )
    flow._notify_progress("exec_summary_iteration", {
        "iteration": 1,
        "max_iterations": max_iter,
        "chars": len(current_content),
    })

    # ── Post-initial-draft user feedback (optional) ───────
    pending_user_feedback: str | None = None
    user_fb_cb = flow._resolve_callback("exec_summary_user_feedback_callback")
    if user_fb_cb is not None:
        pending_user_feedback = exec_summary_user_gate(
            flow, current_content, 1,
        )
        if pending_user_feedback is False:  # type: ignore[comparison-overlap]
            # User approved — skip the critique loop entirely
            return

    # ── Critique → iterate loop ──────────────────────────
    # Assembles unique agent lists for multi-agent Crews.
    # The critique Crew only uses the critic agent (lightweight).
    # The refine Crew only uses the primary PM (research-tier).
    critique_crew_agents = [critic]
    refine_crew_agents = [pm]
    iteration = 1
    while iteration < max_iter:
        # --- Critique (uses secondary agent when available) ---
        logger.info(
            "[ExecSummary] Critique iteration %d/%d (agent=%s)",
            iteration, max_iter, critic_name,
        )
        critique_task = Task(
            description=task_configs["critique_prd_task"]["description"].format(
                critique="(generate critique)",
                executive_summary=current_content,
            ),
            expected_output=task_configs["critique_prd_task"][
                "expected_output"
            ],
            agent=critic,
        )
        crew = Crew(
            agents=critique_crew_agents,
            tasks=[critique_task],
            process=Process.sequential,
            verbose=is_verbose(),
        )
        try:
            critique_result = crew_kickoff_with_retry(
                crew, step_label=f"critique_exec_summary_iter{iteration}",
            )
        except (BillingError, ModelBusyError):
            raise  # Non-transient — must pause
        except Exception as exc:
            logger.error(
                "[ExecSummary] Critique failed at iteration %d: %s",
                iteration, exc,
            )
            save_failed(
                run_id=flow.state.run_id,
                idea=user_idea,
                iteration=iteration,
                error=str(exc),
                step=f"critique_exec_summary_iter{iteration}",
            )
            logger.warning(
                "[ExecSummary] Critique unrecoverable at iteration "
                "%d — force-approving with current content (%d chars)",
                iteration, len(current_content),
            )
            flow.state.executive_summary.is_approved = True
            break

        critique_text = critique_result.raw

        # Update critique on the current iteration record
        update_executive_summary_critique(
            run_id=flow.state.run_id,
            iteration=iteration,
            critique=critique_text,
        )
        # Update in-memory model
        current_iter = flow.state.executive_summary.iterations[-1]
        current_iter.critique = critique_text
        flow.state.critique = critique_text

        # --- Check termination ----
        is_ready = "READY_FOR_DEV" in critique_text.upper()
        past_min = iteration >= min_iter

        if is_ready and past_min:
            logger.info(
                "[ExecSummary] READY_FOR_DEV at iteration %d "
                "(min=%d) — approved",
                iteration, min_iter,
            )
            flow.state.executive_summary.is_approved = True
            break

        # --- Produce refined version — primary PM addresses
        #     critique from the secondary agent (cross-agent
        #     collaboration: one agent critiques, another refines) ---
        iteration += 1
        refine_desc = task_configs["draft_prd_task"]["description"].format(
            idea=flow.state.idea,
            executive_summary=current_content,
        )
        refine_desc += (
            f"\n\n--- CRITIQUE FEEDBACK ---\n{critique_text}\n"
            f"--- END OF CRITIQUE ---\n\n"
            "Address every gap identified in the critique above. "
            "Produce an improved executive summary."
        )
        # Append any pending user feedback so the refine step
        # incorporates both AI critique *and* user guidance.
        if pending_user_feedback:
            refine_desc += (
                f"\n\n--- USER FEEDBACK ---\n{pending_user_feedback}\n"
                "--- END OF USER FEEDBACK ---\n\n"
                "Also incorporate the user's feedback above."
            )
            pending_user_feedback = None  # consumed
        refine_task = Task(
            description=refine_desc,
            expected_output=task_configs["draft_prd_task"][
                "expected_output"
            ],
            agent=pm,
        )
        crew = Crew(
            agents=refine_crew_agents,
            tasks=[refine_task],
            process=Process.sequential,
            verbose=is_verbose(),
        )
        try:
            refine_result = crew_kickoff_with_retry(
                crew,
                step_label=f"refine_exec_summary_iter{iteration}",
            )
        except (BillingError, ModelBusyError):
            raise  # Non-transient — must pause
        except Exception as exc:
            logger.error(
                "[ExecSummary] Refine failed at iteration %d: %s",
                iteration, exc,
            )
            save_failed(
                run_id=flow.state.run_id,
                idea=user_idea,
                iteration=iteration,
                error=str(exc),
                step=f"refine_exec_summary_iter{iteration}",
            )
            logger.warning(
                "[ExecSummary] Refine unrecoverable at iteration "
                "%d — force-approving with current content (%d chars)",
                iteration, len(current_content),
            )
            flow.state.executive_summary.is_approved = True
            break

        current_content = refine_result.raw

        # Guard: strip JSON document dumps the LLM may produce
        current_content = sanitize_section_content(
            current_content, "executive_summary",
        )

        now = datetime.now(timezone.utc).isoformat()
        new_iter = ExecutiveSummaryIteration(
            content=current_content,
            iteration=iteration,
            critique=None,
            updated_date=now,
        )
        flow.state.executive_summary.iterations.append(new_iter)
        flow.state.iteration = iteration
        flow.state.update_date = now

        save_executive_summary(
            run_id=flow.state.run_id,
            idea=user_idea,
            iteration=iteration,
            content=current_content,
            critique=None,
        )
        logger.info(
            "[ExecSummary] Refined iteration %d (%d chars)",
            iteration, len(current_content),
        )
        flow._notify_progress("exec_summary_iteration", {
            "iteration": iteration,
            "max_iterations": max_iter,
            "chars": len(current_content),
            "critique_summary": (critique_text or "")[:500],
        })

        # ── Post-iteration user feedback (optional) ──────
        user_fb_cb = flow._resolve_callback("exec_summary_user_feedback_callback")
        if user_fb_cb is not None:
            pending_user_feedback = exec_summary_user_gate(
                flow, current_content, iteration,
            )
            if pending_user_feedback is False:  # type: ignore[comparison-overlap]
                # User approved — stop iterating
                return

    # Force-approve if max reached without READY_FOR_DEV
    if not flow.state.executive_summary.is_approved:
        flow.state.executive_summary.is_approved = True
        logger.info(
            "[ExecSummary] Max iterations (%d) reached — "
            "force-approved",
            max_iter,
        )

    # Copy the last iterated executive summary to finalized_idea
    flow.state.finalized_idea = flow.state.executive_summary.latest_content
    save_finalized_idea(
        run_id=flow.state.run_id,
        finalized_idea=flow.state.finalized_idea,
    )
    logger.info(
        "[ExecSummary] Copied executive summary to finalized_idea "
        "(%d chars)",
        len(flow.state.finalized_idea),
    )
    flow._notify_progress("executive_summary_complete", {
        "iterations": len(flow.state.executive_summary.iterations),
        "chars": len(flow.state.finalized_idea),
    })


__all__ = [
    "exec_summary_user_gate",
    "iterate_executive_summary",
]
