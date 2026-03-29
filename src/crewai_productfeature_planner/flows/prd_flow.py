"""Iterative PRD generation flow with multi-agent parallel analysis.

Implements a section-by-section PRD workflow with support for multiple
LLM agents running in parallel:

  0. Idea Refinement — A Gemini-powered agent adopts an industry-expert
     persona and iteratively enriches the raw idea (3-10 cycles) before
     PRD drafting begins.
  1. Initial Draft — Multiple agents (one per LLM provider, e.g. OpenAI + Gemini
     when available) each draft the section simultaneously.  The user picks
     which result to use.
  2. Self-Critique — The selected agent evaluates the chosen draft.
  3. Refinement — The selected agent addresses every gap found.
  4. Final Assembly — Once all sections are approved, the full PRD is assembled.

The user must approve each section before the flow moves to the next one.
Each iteration is persisted to MongoDB (``ideas.workingIdeas``).
The assembled final PRD is saved and the working idea marked completed.

Sub-modules (extracted for modularity):
    - ``_constants.py``        — constants, utility functions, exceptions, state model
    - ``_agents.py``           — agent creation, parallel execution, decision parsing
    - ``_executive_summary.py`` — Phase 1 executive summary iteration
    - ``_section_loop.py``     — Phase 2 section critique→refine loop
    - ``_finalization.py``     — save, finalize, post-completion delivery
"""

import os
from datetime import datetime, timezone
from typing import Callable

from crewai import Agent, Crew, Task
from crewai.flow.flow import Flow, start

from crewai_productfeature_planner.agents.product_manager import (
    create_product_manager,
    create_product_manager_critic,
    get_task_configs,
)
from crewai_productfeature_planner.apis.prd.models import (
    ExecutiveSummaryIteration,  # noqa: F401 — re-exported for test compat
    PRDDraft,
    get_default_agent,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger
from crewai_productfeature_planner.scripts.memory_loader import resolve_project_id
from crewai_productfeature_planner.scripts.retry import crew_kickoff_with_retry
from crewai_productfeature_planner.tools.file_write_tool import PRDFileWriteTool
from crewai_productfeature_planner.mongodb import (
    get_output_file,
    mark_completed,
    mark_paused,
    save_executive_summary,
    save_failed,
    save_finalized_idea,
    save_iteration,
    save_output_file,
    update_executive_summary_critique,
    update_section_critique,
)

# Re-export all public names from sub-modules so existing imports work.
from crewai_productfeature_planner.flows._constants import (  # noqa: F401
    PAUSE_SENTINEL,
    DEFAULT_MIN_SECTION_ITERATIONS,
    DEFAULT_MAX_SECTION_ITERATIONS,
    DEFAULT_EXEC_RESUME_THRESHOLD,
    DEFAULT_MULTI_AGENTS,
    DEFAULT_SECTION_MAX_CHARS,
    DEFAULT_SECTION_GROWTH_FACTOR,
    ApprovalDecision,
    PauseRequested,
    IdeaFinalized,
    RequirementsFinalized,
    ExecutiveSummaryCompleted,
    PRDState,
    _get_section_iteration_limits,
    _is_degenerate_content,
)
from crewai_productfeature_planner.flows._agents import (
    get_available_agents as _get_available_agents_fn,
    run_agents_parallel as _run_agents_parallel_fn,
    parse_decision as _parse_decision_fn,
)
from crewai_productfeature_planner.flows._executive_summary import (
    exec_summary_user_gate as _exec_summary_user_gate_fn,
    iterate_executive_summary as _iterate_executive_summary_fn,
)
from crewai_productfeature_planner.flows._section_loop import (
    section_approval_loop as _section_approval_loop_fn,
)
from crewai_productfeature_planner.flows._ceo_eng_review import (
    run_ceo_review as _run_ceo_review_fn,
    run_eng_plan as _run_eng_plan_fn,
)
from crewai_productfeature_planner.flows._finalization import (
    save_progress as _save_progress_fn,
    persist_output_path as _persist_output_path_fn,
    finalize as _finalize_fn,
    run_post_completion as _run_post_completion_fn,
    persist_post_completion as _persist_post_completion_fn,
    extract_confluence_url as _extract_confluence_url_fn,
    jira_detected_in_output as _jira_detected_in_output_fn,
)

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Module-level callback registry — safety net for CrewAI Flow execution.
#
# CrewAI Flow runs @start() methods via asyncio.to_thread which can lose
# instance attributes set after __init__ (e.g. callbacks assigned in
# run_prd_flow).  This registry persists callbacks keyed by run_id so
# generate_sections() can retrieve them regardless.
# ---------------------------------------------------------------------------
_callback_registry: dict[str, dict] = {}


def register_callbacks(run_id: str, **callbacks) -> None:
    """Store callbacks in the module-level registry for *run_id*."""
    _callback_registry[run_id] = callbacks
    logger.debug(
        "[CallbackRegistry] Registered %d callback(s) for run_id=%s: %s",
        len(callbacks), run_id, list(callbacks.keys()),
    )


def _get_registered_callback(run_id: str, name: str):
    """Retrieve a callback from the registry (or ``None``)."""
    return _callback_registry.get(run_id, {}).get(name)


def cleanup_callbacks(run_id: str) -> None:
    """Remove callbacks for *run_id* from the registry."""
    if _callback_registry.pop(run_id, None) is not None:
        logger.debug("[CallbackRegistry] Cleaned up run_id=%s", run_id)


class PRDFlow(Flow[PRDState]):
    """CrewAI Flow that drafts, critiques, and refines a PRD section by section.

    The flow processes sections in a fixed order, starting with Executive
    Summary.  Each approved section is used as context for subsequent ones.

    When ``GOOGLE_API_KEY`` or ``GOOGLE_CLOUD_PROJECT`` is set in the
    environment, the flow creates Gemini-powered agents for idea
    refinement and requirements breakdown phases.

    Args:
        approval_callback: An optional callable::

            (iteration, section_key, agent_results, draft) -> ApprovalDecision

        *agent_results* is ``dict[str, str]`` mapping agent names
        (``"openai"``) to their draft content.

        Return values:

        - ``(agent_name, True)``  — approve using that agent's result.
        - ``(agent_name, False)`` — refine using that agent's result.
        - ``(agent_name, "feedback")`` — refine with user feedback.
        - ``True`` / ``False`` / ``"feedback"`` — legacy single-agent
          shorthand (selects first available agent automatically).
        - ``"__PAUSE__"`` — pause the flow.

        When *not* set the flow auto-approves after the agent marks
        the section as ``SECTION_READY``.
    """

    approval_callback: (
        Callable[[int, str, dict[str, str], PRDDraft], ApprovalDecision] | None
    ) = None

    # Callback invoked after idea refinement (manual or agent) completes.
    # Signature: (refined_idea, original_idea, run_id, refinement_history) -> bool
    # Return True  → finalize the idea (save & stop, no PRD generation).
    # Return False → continue to PRD generation.
    idea_approval_callback: (
        Callable[[str, str, str, list[dict]], bool] | None
    ) = None

    # Callback invoked after requirements breakdown completes.
    # Signature: (requirements, idea, run_id, breakdown_history) -> bool
    # Return True  → finalize the requirements (save & stop, no PRD).
    # Return False → continue to PRD generation with enriched context.
    requirements_approval_callback: (
        Callable[[str, str, str, list[dict]], bool] | None
    ) = None

    # Callback invoked after executive summary iteration completes.
    # Signature: (executive_summary, idea, run_id, iterations) -> bool
    # Return True  → continue to section-level drafting.
    # Return False → stop after the executive summary (raise ExecutiveSummaryCompleted).
    executive_summary_callback: (
        Callable[[str, str, str, list[dict]], bool] | None
    ) = None

    # Per-iteration user feedback callback for the executive summary.
    #
    # Called at two points inside _iterate_executive_summary():
    # 1. **Pre-draft** (iteration=0, content=""):
    #    Asks the user whether they want to provide initial guidance.
    #    Return ("skip", None)     → proceed without guidance.
    #    Return ("feedback", text) → inject *text* into the initial draft prompt.
    #
    # 2. **After each iteration** (iteration>=1, content=current_summary):
    #    Shows the user the current executive summary.
    #    Return ("approve", None)  → user is satisfied; stop iterating.
    #    Return ("feedback", text) → incorporate *text* into the next refine step.
    #
    # Signature: (content, idea, run_id, iteration) -> tuple[str, str | None]
    exec_summary_user_feedback_callback: (
        Callable[[str, str, str, int], tuple[str, str | None]] | None
    ) = None

    # Progress / heartbeat callback.
    # Signature: (event_type: str, details: dict) -> None
    # Fired at key milestones so callers (e.g. Slack) can push live updates.
    progress_callback: (
        Callable[[str, dict], None] | None
    ) = None

    # Jira skeleton approval callback — phased Jira flow (Phase 1).
    # Called after skeleton generation with the raw skeleton text.
    # Signature: (skeleton_text, run_id) -> tuple[str, str | None]
    # Return ("approve", None)           → proceed to Phase 2.
    # Return ("approve", edited_skeleton) → proceed with user edits.
    # Return ("reject", None)            → skip Jira ticketing entirely.
    jira_skeleton_approval_callback: (
        Callable[[str, str], tuple[str, str | None]] | None
    ) = None

    # Jira review callback — phased Jira flow (Phase 2 → Phase 3).
    # Called after Epics & Stories are created so the user can review
    # before sub-task generation.
    # Signature: (epics_stories_output, run_id) -> bool
    # Return True  → proceed to Phase 3 (sub-task creation).
    # Return False → skip sub-task creation.
    jira_review_callback: (
        Callable[[str, str], bool] | None
    ) = None

    # ------------------------------------------------------------------
    # Callback resolution — instance attribute with registry fallback
    # ------------------------------------------------------------------
    def _resolve_callback(self, name: str):
        """Return the callback for *name*, falling back to the registry.

        CrewAI Flow runs ``@start()`` methods via ``asyncio.to_thread``
        which can lose instance attributes set after ``__init__``.
        The module-level ``_callback_registry`` is populated by
        ``run_prd_flow()`` as a safety net.
        """
        # 1. Instance attribute (fast path — works when CrewAI behaves)
        value = getattr(self, name, None)
        if value is not None:
            return value
        # 2. Module-level registry (fallback)
        run_id = getattr(getattr(self, "state", None), "run_id", "") or ""
        if run_id:
            value = _get_registered_callback(run_id, name)
            if value is not None:
                logger.info(
                    "[CallbackRegistry] Recovered '%s' from registry "
                    "for run_id=%s (instance attr was None)",
                    name, run_id,
                )
                # Re-attach so subsequent lookups skip the registry
                setattr(self, name, value)
                return value
        return None

    # ------------------------------------------------------------------
    # Helper — notify progress
    # ------------------------------------------------------------------
    def _notify_progress(self, event_type: str, details: dict | None = None) -> None:
        """Fire the progress callback if set, swallowing errors."""
        cb = self._resolve_callback("progress_callback")
        if cb is not None:
            try:
                cb(event_type, details or {})
            except Exception:  # noqa: BLE001
                logger.debug("progress_callback failed for %s", event_type, exc_info=True)

    # ------------------------------------------------------------------
    # Delegating methods — thin wrappers around extracted functions
    # ------------------------------------------------------------------

    @staticmethod
    def _get_available_agents(
        project_id: str | None = None,
    ) -> dict[str, Agent]:
        """Return a dict of agent-name → Agent for all available LLMs."""
        return _get_available_agents_fn(project_id=project_id)

    @staticmethod
    def _run_agents_parallel(
        agents: dict[str, Agent],
        task_configs: dict,
        section_title: str,
        idea: str,
        section_content: str,
        executive_summary: str,
        executive_product_summary: str = "",
        engineering_plan: str = "",
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Execute draft tasks across *agents* in parallel."""
        return _run_agents_parallel_fn(
            agents=agents,
            task_configs=task_configs,
            section_title=section_title,
            idea=idea,
            section_content=section_content,
            executive_summary=executive_summary,
            executive_product_summary=executive_product_summary,
            engineering_plan=engineering_plan,
        )

    @staticmethod
    def _parse_decision(
        decision: ApprovalDecision,
        available_agents: list[str],
    ) -> tuple[str, bool | str]:
        """Normalise an *ApprovalDecision* into ``(agent_name, action)``."""
        return _parse_decision_fn(decision, available_agents)

    # ------------------------------------------------------------------
    # Step 0 — Idea Refinement (Gemini-only, optional)
    # ------------------------------------------------------------------
    def _maybe_refine_idea(self) -> None:
        """Run the Gemini-powered idea refiner if credentials are available.

        The refiner iteratively enriches the raw idea (3-10 cycles)
        from the perspective of an industry-expert user.  Skipped when
        Gemini credentials are missing or when the idea was already
        refined (e.g. resumed run).
        """
        if self.state.idea_refined:
            logger.info("[IdeaRefiner] Skipping — idea already refined")
            return

        # Only run when Gemini credentials are present
        has_api_key = bool(os.environ.get("GOOGLE_API_KEY"))
        has_project = bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))
        if not has_api_key and not has_project:
            logger.info(
                "[IdeaRefiner] Skipping — no GOOGLE_API_KEY or "
                "GOOGLE_CLOUD_PROJECT set"
            )
            return

        logger.info("[IdeaRefiner] Refining idea before PRD generation")
        try:
            from crewai_productfeature_planner.agents.idea_refiner import refine_idea

            self.state.original_idea = self.state.idea
            project_id = resolve_project_id(self.state.run_id)
            refined, history = refine_idea(
                self.state.idea,
                run_id=self.state.run_id,
                project_id=project_id,
            )
            self.state.idea = refined
            self.state.idea_refined = True
            self.state.refinement_history = history
            logger.info(
                "[IdeaRefiner] Idea refined (%d → %d chars, %d iterations)",
                len(self.state.original_idea), len(refined), len(history),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[IdeaRefiner] Refinement failed: %s — continuing with "
                "original idea",
                exc,
            )

    # ------------------------------------------------------------------
    # Phase 1 helper — Executive Summary
    # ------------------------------------------------------------------
    def _exec_summary_user_gate(
        self, content: str, iteration: int,
    ) -> str | None | bool:
        """Prompt the user for feedback after an exec summary iteration."""
        return _exec_summary_user_gate_fn(self, content, iteration)

    def _iterate_executive_summary(
        self, agents: dict[str, Agent], task_configs: dict,
        *, critic_agent: Agent | None = None,
    ) -> None:
        """Draft and iterate the executive summary."""
        _iterate_executive_summary_fn(
            self, agents, task_configs, critic_agent=critic_agent,
        )

    # ------------------------------------------------------------------
    # Phase 2 helper — Section approval loop
    # ------------------------------------------------------------------
    def _section_approval_loop(
        self, section, agents: dict[str, Agent], task_configs,
        *, critic_agent: Agent | None = None,
    ) -> None:
        """Iterate a single section through critique→refine cycles."""
        _section_approval_loop_fn(
            self, section, agents, task_configs,
            critic_agent=critic_agent,
        )

    # ------------------------------------------------------------------
    # Phase 1.5 — CEO Review, Engineering Plan & UX Design (gstack agents)
    # ------------------------------------------------------------------
    def _run_ceo_review(self) -> str:
        """Generate Executive Product Summary via the CEO Reviewer agent."""
        return _run_ceo_review_fn(self)

    def _run_eng_plan(self) -> str:
        """Generate Engineering Plan via the Eng Manager agent."""
        return _run_eng_plan_fn(self)

    # ------------------------------------------------------------------
    # Step 1 — Executive Summary iteration → then section drafting
    # ------------------------------------------------------------------
    @start()
    def generate_sections(self) -> str:
        """Run the agent pipeline, iterate the executive summary, then draft sections."""
        # ── Early cancellation check ──
        from crewai_productfeature_planner.apis.shared import check_cancelled
        check_cancelled(self.state.run_id)

        # ── Agent pipeline (idea refinement → requirements → …) ──
        from crewai_productfeature_planner.orchestrator import (
            build_default_pipeline,
        )

        orchestrator = build_default_pipeline(self)
        orchestrator.run_pipeline()

        # ── Cancellation checkpoint (after pipeline) ──
        from crewai_productfeature_planner.apis.shared import check_cancelled
        check_cancelled(self.state.run_id)
        # This helps debug cases where CrewAI's asyncio.to_thread loses
        # instance attributes set before kickoff().
        logger.info(
            "[Callbacks] exec_summary_user_feedback=%s, "
            "executive_summary=%s, requirements_approval=%s, "
            "progress=%s, run_id=%s",
            self.exec_summary_user_feedback_callback is not None,
            self.executive_summary_callback is not None,
            self.requirements_approval_callback is not None,
            self.progress_callback is not None,
            self.state.run_id,
        )

        # Resolve project_id for memory enrichment across all agents
        project_id = resolve_project_id(self.state.run_id)

        agents = self._get_available_agents(project_id=project_id)
        task_configs = get_task_configs()

        # Create a lightweight critic agent once; reused for all
        # critique tasks in both Phase 1 (exec summary) and Phase 2
        # (section loop).  Falls back to None when Gemini credentials
        # are missing — the critique functions will self-critique.
        critic_agent: Agent | None = None
        try:
            critic_agent = create_product_manager_critic(
                project_id=project_id,
            )
            logger.info(
                "[Agents] Lightweight critic agent created "
                "(flash model, no tools)",
            )
        except EnvironmentError:
            logger.info(
                "[Agents] Critic agent unavailable — no Gemini "
                "credentials; critique will use the primary PM agent",
            )

        # Track initial agent roster
        self.state.active_agents = list(agents.keys())
        self.state.dropped_agents = []

        # Set lifecycle status fields
        if not self.state.created_at:
            self.state.created_at = datetime.now(timezone.utc).isoformat()
        self.state.status = "inprogress"
        self.state.update_date = datetime.now(timezone.utc).isoformat()

        # ── Check if Phase 1 can be skipped (resumed run) ────
        exec_resume_threshold = int(os.environ.get(
            "PRD_EXEC_RESUME_THRESHOLD",
            str(DEFAULT_EXEC_RESUME_THRESHOLD),
        ))
        existing_iters = len(self.state.executive_summary.iterations)
        # If any section beyond executive_summary and specialist sections
        # already has content, the flow previously completed Phase 1
        # and entered Phase 2.
        from crewai_productfeature_planner.apis.prd._sections import (
            SPECIALIST_SECTION_KEYS,
        )
        _skip_keys = {"executive_summary"} | SPECIALIST_SECTION_KEYS
        has_section_content = any(
            s.content for s in self.state.draft.sections
            if s.key not in _skip_keys
        )
        skip_phase1 = (
            existing_iters >= exec_resume_threshold
            or has_section_content
        )

        if skip_phase1:
            logger.info(
                "[Phase 1] Skipping iteration — executive summary already has "
                "%d iteration(s) (threshold=%d, sections_with_content=%s). "
                "Using last iteration as context for section drafting.",
                existing_iters,
                exec_resume_threshold,
                has_section_content,
            )
            # Ensure the executive summary is marked approved
            self.state.executive_summary.is_approved = True
            self.state.finalized_idea = (
                self.state.executive_summary.latest_content
            )
        else:
            # ── Phase 1: Executive Summary iteration ─────────────
            check_cancelled(self.state.run_id)
            logger.info(
                "[Phase 1] Iterating executive summary for idea: '%s'",
                self.state.idea[:80],
            )
            self._iterate_executive_summary(
                agents, task_configs, critic_agent=critic_agent,
            )

        # ── Requirements Breakdown (runs after exec summary approval) ──
        check_cancelled(self.state.run_id)
        from crewai_productfeature_planner.orchestrator._requirements import (
            build_requirements_breakdown_stage,
        )

        req_stage = build_requirements_breakdown_stage(self)
        if not req_stage.should_skip():
            logger.info(
                "[Requirements] Running requirements breakdown after "
                "executive summary approval",
            )
            req_result = req_stage.run()
            req_stage.apply(req_result)
        else:
            logger.info(
                "[Requirements] Skipping — already broken down or "
                "no credentials",
            )

        # Approval gate — fires for both completed AND skipped stages
        # (a resumed run may have requirements already broken down but
        # needs the user to approve before proceeding to sections).
        if (
            req_stage.get_approval is not None
            and req_stage.requires_approval is not None
            and req_stage.requires_approval()
        ):
            should_finalize = req_stage.get_approval()
            if should_finalize and req_stage.finalized_exc is not None:
                logger.info(
                    "[Requirements] User finalized at requirements approval"
                )
                raise req_stage.finalized_exc()

        # ── Phase 1.5a: CEO Review → Executive Product Summary ───
        check_cancelled(self.state.run_id)
        specialists_all_skipped = True
        if not self.state.executive_product_summary:
            specialists_all_skipped = False
            logger.info(
                "[Phase 1.5a] Running CEO review to generate "
                "Executive Product Summary",
            )
            self._run_ceo_review()
        else:
            logger.info(
                "[Phase 1.5a] Skipping CEO review — executive product "
                "summary already present (%d chars)",
                len(self.state.executive_product_summary),
            )
            # Ensure the section is marked approved for the draft loop
            eps_section = self.state.draft.get_section(
                "executive_product_summary",
            )
            if eps_section is not None and not eps_section.is_approved:
                eps_section.content = self.state.executive_product_summary
                eps_section.is_approved = True

        # ── Phase 1.5b: Eng Manager → Engineering Plan ───────────
        check_cancelled(self.state.run_id)
        if not self.state.engineering_plan:
            specialists_all_skipped = False
            logger.info(
                "[Phase 1.5b] Running Eng Manager to generate "
                "Engineering Plan",
            )
            self._run_eng_plan()
        else:
            logger.info(
                "[Phase 1.5b] Skipping Eng Plan — already present "
                "(%d chars)",
                len(self.state.engineering_plan),
            )
            eng_section = self.state.draft.get_section("engineering_plan")
            if eng_section is not None and not eng_section.is_approved:
                eng_section.content = self.state.engineering_plan
                eng_section.is_approved = True

        # ── Phase 1.5c removed — UX Design is now a separate
        # post-PRD flow triggered after finalization.  See
        # flows/ux_design_flow.py for the standalone 2-phase UX flow.

        # ── User decision gate — proceed to section drafting? ────
        # Fires after all specialist agents (CEO, Eng, UX) have run so
        # the user can review requirements, executive product summary,
        # engineering plan, and Figma design before committing.
        # On resume, skip the gate when all specialists were already done
        # (user approved in a prior run), or when Phase 2 sections
        # already have content (flow previously entered Phase 2).
        exec_cb = self._resolve_callback("executive_summary_callback")
        if exec_cb is not None and not (specialists_all_skipped or has_section_content):
            continue_to_sections = exec_cb(
                self.state.executive_summary.latest_content,
                self.state.idea,
                self.state.run_id,
                [
                    {
                        "iteration": it.iteration,
                        "content": it.content,
                        "critique": it.critique,
                    }
                    for it in self.state.executive_summary.iterations
                ],
            )
            if not continue_to_sections:
                logger.info(
                    "[Phase 1.5] User chose not to continue to sections — "
                    "stopping after specialist agents"
                )
                raise ExecutiveSummaryCompleted()
        else:
            if specialists_all_skipped or has_section_content:
                logger.info(
                    "[Phase 1.5] Skipping user decision gate — resumed "
                    "run (specialists_skipped=%s, sections_started=%s)",
                    specialists_all_skipped, has_section_content,
                )
            else:
                logger.info(
                    "[Phase 1.5] No executive_summary_callback set — "
                    "auto-continuing to section drafting"
                )

        # ── Phase 2: Section-by-section drafting ─────────────
        # Carry the Phase 1 executive summary into the PRDDraft so it
        # is not re-drafted by the section loop.
        exec_section = self.state.draft.get_section("executive_summary")
        if exec_section is not None and not exec_section.is_approved:
            exec_section.content = self.state.executive_summary.latest_content
            exec_section.is_approved = True
            exec_section.iteration = len(self.state.executive_summary.iterations)
            exec_section.updated_date = datetime.now(timezone.utc).isoformat()
            logger.info(
                "[Phase 2] Populated executive_summary section from "
                "Phase 1 (%d chars, %d iterations) — marked approved",
                len(exec_section.content),
                exec_section.iteration,
            )

        logger.info(
            "[Phase 2] Generating PRD sections for idea: '%s'",
            self.state.idea[:80],
        )

        for section in self.state.draft.sections:
            # ── Cancellation checkpoint (before each section) ──
            check_cancelled(self.state.run_id)

            # Skip sections already approved (e.g. executive_summary
            # completed in Phase 1).
            if section.is_approved:
                logger.info(
                    "[Phase 2] Skipping section '%s' — already approved",
                    section.title,
                )
                continue

            self.state.current_section_key = section.key
            total_steps = len(self.state.draft.sections)

            self._notify_progress("section_start", {
                "section_title": section.title,
                "section_key": section.key,
                "section_step": section.step,
                "total_sections": total_steps,
            })

            # ── Resume guard: skip drafting if section already has
            #    content from a prior run (restored from MongoDB).
            if section.content and section.iteration > 0:
                # If restored content is degenerate (e.g. saved before
                # the guard existed), wipe it and fall through to the
                # normal draft step instead of resuming with garbage.
                if _is_degenerate_content(section.content):
                    logger.warning(
                        "[Phase 2] Section '%s' restored content is "
                        "degenerate (%d chars) — wiping and re-drafting",
                        section.title, len(section.content),
                    )
                    section.content = ""
                    section.iteration = 0
                    section.agent_results = {}
                    section.selected_agent = None
                    section.critique = ""
                else:
                    logger.info(
                        "[Phase 2] Resuming section '%s' at iteration %d "
                        "(%d chars) — skipping draft step",
                        section.title, section.iteration,
                        len(section.content),
                    )
                    # Ensure agent_results is populated so the approval
                    # loop has something to work with.
                    if not section.agent_results:
                        agent_key = section.selected_agent or get_default_agent()
                        section.agent_results = {agent_key: section.content}
                    if not section.selected_agent:
                        section.selected_agent = get_default_agent()
                    self._section_approval_loop(
                        section, agents, task_configs,
                        critic_agent=critic_agent,
                    )
                    self._notify_progress("section_complete", {
                        "section_title": section.title,
                        "section_key": section.key,
                        "section_step": section.step,
                        "total_sections": total_steps,
                        "iterations": section.iteration,
                        "content": section.content,
                    })
                    continue

            logger.info("[Draft] Step %d/%d — Generating section '%s' with %d agent(s)",
                        section.step, total_steps, section.title, len(agents))

            # --- Parallel agent drafting ---
            try:
                agent_results, failed_agents = self._run_agents_parallel(
                    agents=agents,
                    task_configs=task_configs,
                    section_title=section.title,
                    idea=self.state.idea,
                    section_content=section.content,
                    executive_summary=self.state.executive_summary.latest_content,
                    executive_product_summary=self.state.executive_product_summary,
                    engineering_plan=self.state.engineering_plan,
                )
            except Exception as exc:
                logger.error("[Draft] Section '%s' generation failed: %s",
                             section.title, exc)
                save_failed(
                    run_id=self.state.run_id,
                    idea=self.state.original_idea or self.state.idea,
                    iteration=section.iteration,
                    error=str(exc),
                    step=f"draft_{section.key}",
                    section_key=section.key,
                    section_title=section.title,
                )
                raise

            section.agent_results = agent_results
            # Default content to the default agent's result (guaranteed
            # to be first in agent_results thanks to reordering in
            # _run_agents_parallel).
            default = get_default_agent()
            first_agent = default if default in agent_results else next(iter(agent_results))
            draft_content = agent_results[first_agent]

            # ── Degenerate draft guard ─────────────────────
            if _is_degenerate_content(draft_content):
                logger.warning(
                    "[Draft] Section '%s' degenerate draft detected "
                    "(%d chars) — substituting placeholder",
                    section.title, len(draft_content),
                )
                draft_content = (
                    f"# {section.title}\n\n"
                    "(Draft content was too large and has been "
                    "replaced — the refine step will generate "
                    "proper content.)"
                )
                agent_results[first_agent] = draft_content

            section.content = draft_content
            section.selected_agent = first_agent
            section.iteration = 1
            section.updated_date = datetime.now(timezone.utc).isoformat()
            self.state.iteration += 1
            self.state.update_date = section.updated_date

            # Drop failed optional agents for the rest of the flow
            default = get_default_agent()
            for name, error_msg in failed_agents.items():
                if name != default and name in agents:
                    del agents[name]
                    if name not in self.state.dropped_agents:
                        self.state.dropped_agents.append(name)
                    self.state.agent_errors[name] = error_msg
                    logger.warning(
                        "[Agents] Removed failed optional agent '%s' (%s) — "
                        "continuing with %d agent(s)",
                        name, error_msg, len(agents),
                    )
            self.state.active_agents = list(agents.keys())

            # Persist section draft
            save_iteration(
                run_id=self.state.run_id,
                idea=self.state.original_idea or self.state.idea,
                iteration=section.iteration,
                draft={section.key: section.content},
                step=f"draft_{section.key}",
                finalized_idea=self.state.idea,
                section_key=section.key,
                section_title=section.title,
                agent_results=agent_results,
            )

            logger.info("[Draft] Step %d/%d — Section '%s' generated (%d chars, %d agent(s))",
                        section.step, total_steps, section.title,
                        len(section.content), len(agent_results))

            # --- Section approval loop ---
            self._section_approval_loop(
                section, agents, task_configs,
                critic_agent=critic_agent,
            )
            self._notify_progress("section_complete", {
                "section_title": section.title,
                "section_key": section.key,
                "section_step": section.step,
                "total_sections": total_steps,
                "iterations": section.iteration,
                "content": section.content,
            })

        logger.info("[Steps 1-3] All sections completed, total iterations=%d",
                    self.state.iteration)
        self._notify_progress("all_sections_complete", {
            "total_iterations": self.state.iteration,
            "total_sections": total_steps,
        })
        return self.finalize()

    # ------------------------------------------------------------------
    # Save / finalize / post-completion — delegated to _finalization.py
    # ------------------------------------------------------------------

    def save_progress(self) -> str:
        """Write a progress markdown capturing whatever work is available."""
        return _save_progress_fn(self)

    def _persist_output_path(self, save_result: str) -> None:
        """Extract the file path from *save_result* and store it in MongoDB."""
        _persist_output_path_fn(self, save_result)

    def finalize(self) -> str:
        """Assemble the final PRD from all approved sections and persist."""
        return _finalize_fn(self)

    def _run_post_completion(self) -> None:
        """Run Atlassian delivery crew after PRD finalization."""
        _run_post_completion_fn(self)

    def _run_auto_post_completion(self) -> None:
        """Run the single post-completion crew (auto-approve mode)."""
        from crewai_productfeature_planner.flows._finalization import (
            _run_auto_post_completion,
        )
        _run_auto_post_completion(self)

    def _run_phased_post_completion(self) -> None:
        """Run phased Confluence + Jira delivery with approval gates."""
        from crewai_productfeature_planner.flows._finalization import (
            _run_phased_post_completion,
        )
        _run_phased_post_completion(self)

    def _persist_post_completion(self, result: object) -> None:
        """Parse crew *result* and update the delivery record."""
        _persist_post_completion_fn(self, result)

    @staticmethod
    def _extract_confluence_url(output: str) -> str:
        """Extract a Confluence URL from crew output text."""
        return _extract_confluence_url_fn(output)

    @staticmethod
    def _jira_detected_in_output(output: str) -> bool:
        """Detect Jira ticket creation in crew output."""
        return _jira_detected_in_output_fn(output)
