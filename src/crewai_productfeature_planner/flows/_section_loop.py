"""Section approval loop for the PRD flow.

Iterates a single PRD section through critique → refine cycles with
optional user approval gates.  Extracted from ``prd_flow.py``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from crewai import Agent, Crew, Process, Task

from crewai_productfeature_planner.apis.prd.models import get_default_agent
from crewai_productfeature_planner.components.document import sanitize_section_content
from crewai_productfeature_planner.flows._constants import (
    PAUSE_SENTINEL,
    PauseRequested,
    _get_section_iteration_limits,
    _is_degenerate_content,
)
from crewai_productfeature_planner.flows._agents import parse_decision
from crewai_productfeature_planner.mongodb import (
    save_failed,
    save_iteration,
    update_section_critique,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger, is_verbose
from crewai_productfeature_planner.scripts.retry import (
    BillingError,
    ModelBusyError,
    ShutdownError,
    crew_kickoff_with_retry,
)

if TYPE_CHECKING:
    from crewai_productfeature_planner.flows.prd_flow import PRDFlow

logger = get_logger(__name__)


def section_approval_loop(
    flow: PRDFlow,
    section,
    agents: dict[str, Agent],
    task_configs,
    *,
    critic_agent: Agent | None = None,
) -> None:
    """Iterate a single section through critique→refine cycles.

    When a dedicated *critic_agent* is supplied, it handles all
    critique tasks — using a lightweight (flash) model with no tools
    for faster evaluation.  Otherwise, falls back to cross-agent
    collaboration or self-critique.

    Each section is automatically iterated between *min* and *max*
    iterations (controlled by ``PRD_SECTION_MIN_ITERATIONS`` /
    ``PRD_SECTION_MAX_ITERATIONS`` env vars, defaulting to 2 / 5).

    * Before *min* is reached the cycle always continues
      (critique → refine → …) regardless of the critique verdict.
    * After *min*, if the critique contains ``SECTION_READY``, the
      section is auto-approved (when no callback is set).
    * At *max*, the section is force-approved regardless.

    When an ``approval_callback`` is configured (API / UI mode) the
    user is given the opportunity to approve, pause, or provide
    feedback at every iteration.  A user-approval overrides the
    minimum-iteration gate.
    """
    min_iter, max_iter = _get_section_iteration_limits()
    total_steps = len(flow.state.draft.sections)

    while not section.is_approved:
        user_feedback: str | None = None
        available = list(section.agent_results.keys()) or list(agents.keys())

        # ── Optional user gate (callback) ─────────────────
        if flow.approval_callback is not None:
            decision = flow.approval_callback(
                section.iteration,
                section.key,
                section.agent_results,
                flow.state.draft,
                active_agents=list(flow.state.active_agents),
                dropped_agents=list(flow.state.dropped_agents),
                agent_errors=dict(flow.state.agent_errors),
                original_idea=flow.state.original_idea,
                idea_refined=flow.state.idea_refined,
                finalized_idea=flow.state.finalized_idea,
                requirements_breakdown=flow.state.requirements_breakdown,
                executive_summary=flow.state.executive_summary,
            )

            agent_name, action = parse_decision(decision, available)

            # Apply selected agent's content
            if agent_name in section.agent_results:
                section.content = section.agent_results[agent_name]
            section.selected_agent = agent_name

            if action is True:
                section.is_approved = True
                logger.info(
                    "[Approval] Step %d/%d — Section '%s' approved "
                    "(agent=%s) at iteration %d",
                    section.step, total_steps, section.title,
                    agent_name, section.iteration,
                )
                break
            if action == PAUSE_SENTINEL or decision == PAUSE_SENTINEL:
                logger.info(
                    "[Pause] User requested pause at step %d/%d "
                    "section '%s' iteration %d",
                    section.step, total_steps, section.title,
                    section.iteration,
                )
                raise PauseRequested()
            if isinstance(action, str) and action.strip():
                user_feedback = action.strip()
                logger.info(
                    "[Approval] User provided critique for section "
                    "'%s' (agent=%s, %d chars)",
                    section.title, agent_name, len(user_feedback),
                )

        # Resolve agent for critique / refine.
        # Cross-agent collaboration: use a different agent for
        # critique when multiple PM agents are available.
        selected = section.selected_agent or available[0]
        pm = agents.get(selected) or next(iter(agents.values()))

        # Pick a critic agent.  Priority:
        #   1) Dedicated lightweight critic (fast model, no tools)
        #   2) Secondary PM agent (cross-agent collaboration)
        #   3) Same PM agent (self-critique)
        if critic_agent is not None:
            critic = critic_agent
        else:
            critic = pm
            for name, agent_obj in agents.items():
                if name != selected:
                    critic = agent_obj
                    break
        critique_crew_agents = [critic]
        refine_crew_agents = [pm]

        # ── Critique (cross-agent when available) ─────────
        if user_feedback is not None:
            flow.state.critique = user_feedback
            section.critique = user_feedback
        else:
            logger.info(
                "[Critique] Step %d/%d — Section '%s' — iteration %d "
                "(agent=%s)",
                section.step, total_steps, section.title,
                section.iteration,
                "critic" if critic_agent is not None
                else next((n for n, a in agents.items() if a is critic), selected),
            )
            # Exclude executive_summary and specialist sections from
            # approved_sections — they are injected separately.
            _excl = {
                section.key, "executive_summary",
                "executive_product_summary", "engineering_plan",
            }
            # Use executive_product_summary when available; fall back to
            # the raw executive_summary for backward compat.
            _eps = flow.state.executive_product_summary or flow.state.executive_summary.latest_content or "(Not yet available)"
            _eng = flow.state.engineering_plan or "(Not yet available)"
            critique_task = Task(
                description=task_configs["critique_section_task"][
                    "description"
                ].format(
                    section_title=section.title,
                    critique_section_content=section.content,
                    executive_product_summary=_eps,
                    engineering_plan=_eng,
                    approved_sections=flow.state.draft.approved_context(exclude_keys=_excl) or "(None yet)",
                ),
                expected_output=task_configs["critique_section_task"][
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
                    crew, step_label=f"critique_{section.key}",
                )
            except (BillingError, ModelBusyError, ShutdownError):
                raise  # Non-transient — must pause
            except Exception as exc:
                logger.error(
                    "[Critique] Section '%s' failed at iteration %d: %s",
                    section.title, section.iteration, exc,
                )
                save_failed(
                    run_id=flow.state.run_id,
                    idea=flow.state.original_idea or flow.state.idea,
                    iteration=flow.state.iteration,
                    error=str(exc),
                    draft={section.key: section.content},
                    step=f"critique_{section.key}",
                    section_key=section.key,
                    section_title=section.title,
                )
                logger.warning(
                    "[Critique] Section '%s' unrecoverable at "
                    "iteration %d — force-approving with current "
                    "content (%d chars)",
                    section.title, section.iteration,
                    len(section.content),
                )
                section.is_approved = True
                break
            flow.state.critique = critique_result.raw
            section.critique = flow.state.critique

        update_section_critique(
            run_id=flow.state.run_id,
            section_key=section.key,
            iteration=section.iteration,
            critique=flow.state.critique,
        )

        # ── Check termination conditions ──────────────────
        is_ready = "SECTION_READY" in flow.state.critique.upper()
        past_min = section.iteration >= min_iter
        at_max = section.iteration >= max_iter

        if at_max:
            section.is_approved = True
            logger.info(
                "[Iteration] Section '%s' reached max iterations "
                "(%d) — auto-approved",
                section.title, max_iter,
            )
            break

        if is_ready and past_min and flow.approval_callback is None:
            section.is_approved = True
            logger.info(
                "[Critique] Section '%s' marked SECTION_READY at "
                "iteration %d (min=%d) — auto-approved",
                section.title, section.iteration, min_iter,
            )
            break

        # ── Refine (primary PM addresses cross-agent critique) ─
        prev_content = section.content  # snapshot for degenerate guard
        logger.info(
            "[Refine] Step %d/%d — Section '%s' — iteration %d",
            section.step, total_steps, section.title,
            section.iteration,
        )
        # Use *condensed* approved context for the refine task.
        # The research model is the latency bottleneck; feeding it
        # the full text of every prior section causes O(n) growth
        # per LLM call.  The condensed version keeps section titles
        # + first 500 chars, enough for consistency without bloat.
        refine_task = Task(
            description=task_configs["refine_section_task"][
                "description"
            ].format(
                section_title=section.title,
                section_content=section.content,
                critique_section_content=flow.state.critique,
                executive_product_summary=_eps,
                engineering_plan=_eng,
                approved_sections=flow.state.draft.approved_context_condensed(exclude_keys=_excl) or "(None yet)",
            ),
            expected_output=task_configs["refine_section_task"][
                "expected_output"
            ].format(
                section_title=section.title,
                critique_section_content=flow.state.critique,
            ),
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
                crew, step_label=f"refine_{section.key}",
            )
        except (BillingError, ModelBusyError, ShutdownError):
            raise  # Non-transient — must pause
        except Exception as exc:
            logger.error(
                "[Refine] Section '%s' failed at iteration %d: %s",
                section.title, section.iteration, exc,
            )
            save_failed(
                run_id=flow.state.run_id,
                idea=flow.state.original_idea or flow.state.idea,
                iteration=flow.state.iteration,
                error=str(exc),
                draft={section.key: section.content},
                step=f"refine_{section.key}",
                section_key=section.key,
                section_title=section.title,
            )
            logger.warning(
                "[Refine] Section '%s' unrecoverable at "
                "iteration %d — force-approving with current "
                "content (%d chars)",
                section.title, section.iteration,
                len(section.content),
            )
            section.is_approved = True
            break
        section.content = refine_result.raw

        # ── JSON document dump guard ────────────────────
        section.content = sanitize_section_content(
            section.content, section.key,
        )

        # ── Degenerate output guard ─────────────────────
        if _is_degenerate_content(
            section.content, prev_len=len(prev_content),
        ):
            degenerate_len = len(section.content)
            section.content = prev_content
            section.agent_results = {
                section.selected_agent: prev_content,
            }

            if section.iteration >= min_iter:
                logger.warning(
                    "[Refine] Section '%s' degenerate output detected "
                    "(%d chars, prev=%d) — "
                    "reverting to previous content and force-approving",
                    section.title, degenerate_len,
                    len(prev_content),
                )
                section.is_approved = True
                break

            logger.warning(
                "[Refine] Section '%s' degenerate output detected "
                "(%d chars, prev=%d) — "
                "reverting to previous content and retrying "
                "(iteration %d < min %d)",
                section.title, degenerate_len,
                len(prev_content), section.iteration, min_iter,
            )
            section.iteration += 1
            section.updated_date = datetime.now(timezone.utc).isoformat()
            flow.state.iteration += 1
            flow.state.update_date = section.updated_date
            continue

        # Update agent_results so subsequent callbacks see refined content
        section.agent_results = {section.selected_agent: section.content}
        section.iteration += 1
        section.updated_date = datetime.now(timezone.utc).isoformat()
        flow.state.iteration += 1
        flow.state.update_date = section.updated_date

        save_iteration(
            run_id=flow.state.run_id,
            idea=flow.state.original_idea or flow.state.idea,
            iteration=section.iteration,
            draft={section.key: section.content},
            critique=flow.state.critique,
            step=f"refine_{section.key}",
            finalized_idea=flow.state.idea,
            section_key=section.key,
            section_title=section.title,
            selected_agent=section.selected_agent,
        )

        logger.debug(
            "[Refine] Section '%s' refined (%d chars)",
            section.title, len(section.content),
        )
        flow._notify_progress("section_iteration", {
            "section_title": section.title,
            "section_key": section.key,
            "section_step": section.step,
            "total_sections": total_steps,
            "iteration": section.iteration,
            "max_iterations": max_iter,
        })


__all__ = [
    "section_approval_loop",
]
