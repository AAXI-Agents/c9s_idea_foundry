"""Iterative PRD generation flow with multi-agent parallel analysis.

Implements a section-by-section PRD workflow with support for multiple
LLM agents running in parallel:

  0. Idea Refinement — A Gemini-powered agent adopts an industry-expert
     persona and iteratively enriches the raw idea (3-10 cycles) before
     PRD drafting begins.
  1. Initial Draft — Multiple agents (OpenAI PM + Gemini PM when available)
     each draft the section simultaneously.  The user picks which result
     to use.
  2. Self-Critique — The selected agent evaluates the chosen draft.
  3. Refinement — The selected agent addresses every gap found.
  4. Final Assembly — Once all sections are approved, the full PRD is assembled.

The user must approve each section before the flow moves to the next one.
Each iteration is persisted to MongoDB (``ideas.workingIdeas``).
The assembled final PRD is saved and the working idea marked completed.
"""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Callable, Union

from crewai import Agent, Crew, Process, Task
from crewai.flow.flow import Flow, start
from pydantic import BaseModel, Field

from crewai_productfeature_planner.agents.gemini_product_manager.agent import (
    create_gemini_product_manager,
)
from crewai_productfeature_planner.agents.product_manager import (
    create_product_manager,
    get_task_configs,
)
from crewai_productfeature_planner.apis.prd.models import (
    AGENT_GEMINI,
    AGENT_OPENAI,
    ExecutiveSummaryDraft,
    ExecutiveSummaryIteration,
    PRDDraft,
    get_default_agent,
)
from crewai_productfeature_planner.scripts.confluence_xhtml import md_to_confluence_xhtml
from crewai_productfeature_planner.scripts.logging_config import get_logger, is_verbose
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
from crewai_productfeature_planner.scripts.retry import crew_kickoff_with_retry
from crewai_productfeature_planner.tools.file_write_tool import PRDFileWriteTool

logger = get_logger(__name__)

PAUSE_SENTINEL = "__PAUSE__"

# Minimum and maximum critique→refine iterations for each PRD section.
# Override via ``PRD_SECTION_MIN_ITERATIONS`` / ``PRD_SECTION_MAX_ITERATIONS``.
DEFAULT_MIN_SECTION_ITERATIONS = 2
DEFAULT_MAX_SECTION_ITERATIONS = 10

# When resuming, skip Phase 1 (executive summary iteration) if the
# document already has at least this many executive summary iterations.
# Override via ``PRD_EXEC_RESUME_THRESHOLD``.
DEFAULT_EXEC_RESUME_THRESHOLD = 3

# How many PM agents to run in parallel for section drafting.
# 1 = default agent only; 2 = default + optional (e.g. Gemini + OpenAI).
# Override via ``DEFAULT_MULTI_AGENTS``.
DEFAULT_MULTI_AGENTS = 1

# Maximum allowed character count for a single PRD section.
# If a refine result exceeds this, it is treated as degenerate LLM
# output (e.g. repetitive "ofofofof…") and the previous version is
# kept.  Override via ``PRD_SECTION_MAX_CHARS``.
DEFAULT_SECTION_MAX_CHARS = 30_000

# If a refine result is more than this multiplier times the previous
# content length, it is considered degenerate.  Override via
# ``PRD_SECTION_GROWTH_FACTOR``.
DEFAULT_SECTION_GROWTH_FACTOR = 5.0


def _get_section_iteration_limits() -> tuple[int, int]:
    """Return ``(min_iterations, max_iterations)`` from env or defaults."""
    min_iter = int(os.environ.get(
        "PRD_SECTION_MIN_ITERATIONS", str(DEFAULT_MIN_SECTION_ITERATIONS),
    ))
    max_iter = int(os.environ.get(
        "PRD_SECTION_MAX_ITERATIONS", str(DEFAULT_MAX_SECTION_ITERATIONS),
    ))
    # Sanity clamp
    min_iter = max(1, min(min_iter, 10))
    max_iter = max(min_iter, min(max_iter, 20))
    return min_iter, max_iter


def _is_degenerate_content(
    content: str,
    prev_len: int = 0,
    *,
    max_chars: int | None = None,
    growth_factor: float | None = None,
) -> bool:
    """Return *True* if *content* looks like degenerate LLM output.

    Two independent triggers:
    1. Absolute size exceeds *max_chars* (env ``PRD_SECTION_MAX_CHARS``).
    2. Size exceeds *prev_len* × *growth_factor*
       (env ``PRD_SECTION_GROWTH_FACTOR``), when *prev_len* > 0.
    """
    if max_chars is None:
        max_chars = int(os.environ.get(
            "PRD_SECTION_MAX_CHARS",
            str(DEFAULT_SECTION_MAX_CHARS),
        ))
    if growth_factor is None:
        growth_factor = float(os.environ.get(
            "PRD_SECTION_GROWTH_FACTOR",
            str(DEFAULT_SECTION_GROWTH_FACTOR),
        ))
    new_len = len(content)
    if new_len > max_chars:
        return True
    if prev_len > 0 and new_len > prev_len * growth_factor:
        return True
    return False


# Type alias for the approval callback return.
#   - True/False       → approve / refine (selects first available agent)
#   - str              → user feedback for refinement
#   - PAUSE_SENTINEL   → pause the flow
#   - (agent, True)    → approve using *agent*'s result
#   - (agent, False)   → refine using *agent*
#   - (agent, str)     → refine with user feedback using *agent*
ApprovalDecision = Union[bool, str, tuple[str, Union[bool, str]]]


class PauseRequested(Exception):
    """Raised when the user requests to pause and save the current iteration."""


class IdeaFinalized(Exception):
    """Raised when the user approves the refined idea without generating a PRD.

    The working idea has been marked as completed by the time this
    is raised.
    """


class RequirementsFinalized(Exception):
    """Raised when the user finalizes the requirements breakdown without PRD.

    The working idea has been marked as completed by the time this
    is raised.
    """


class ExecutiveSummaryCompleted(Exception):
    """Raised when the executive summary iteration is complete.

    The user chose not to continue to section-level drafting.  The
    executive summary has been saved to ``workingIdeas``.
    """


class PRDState(BaseModel):
    """Tracks the evolving PRD through the section-by-section workflow."""

    run_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    idea: str = ""
    draft: PRDDraft = Field(default_factory=PRDDraft.create_empty)
    current_section_key: str = ""
    critique: str = ""
    final_prd: str = ""
    iteration: int = 0
    is_ready: bool = False
    status: str = Field(
        default="new",
        description="Lifecycle status: 'new', 'inprogress', or 'completed'.",
    )
    created_at: str = Field(
        default="",
        description="ISO-8601 timestamp when the run was created.",
    )
    update_date: str = Field(
        default="",
        description="ISO-8601 timestamp of the last update.",
    )
    completed_at: str = Field(
        default="",
        description="ISO-8601 timestamp when the run was completed.",
    )
    active_agents: list[str] = Field(
        default_factory=list,
        description="Agent identifiers currently participating in the flow.",
    )
    dropped_agents: list[str] = Field(
        default_factory=list,
        description="Agent identifiers removed after failing during parallel drafting.",
    )
    agent_errors: dict[str, str] = Field(
        default_factory=dict,
        description="Map of agent name to error message for agents that failed.",
    )
    original_idea: str = Field(
        default="",
        description="The raw idea before refinement (empty when refinement is skipped).",
    )
    idea_refined: bool = Field(
        default=False,
        description="Whether the idea was refined by the Idea Refinement agent.",
    )
    refinement_history: list[dict] = Field(
        default_factory=list,
        description="Iteration history from idea refinement (each dict has 'iteration', 'idea', and optionally 'evaluation').",
    )
    requirements_breakdown: str = Field(
        default="",
        description="Structured product requirements produced by the Requirements Breakdown agent.",
    )
    breakdown_history: list[dict] = Field(
        default_factory=list,
        description="Iteration history from requirements breakdown (each dict has 'iteration', 'requirements', 'evaluation').",
    )
    requirements_broken_down: bool = Field(
        default=False,
        description="Whether the idea has been broken down into requirements.",
    )
    executive_summary: ExecutiveSummaryDraft = Field(
        default_factory=ExecutiveSummaryDraft,
        description="Iterative executive summary produced in the draft phase.",
    )
    finalized_idea: str = Field(
        default="",
        description="Copy of the last iterated executive summary content once Phase 1 completes.",
    )
    confluence_url: str = Field(
        default="",
        description="URL of the Confluence page where the PRD was published.",
    )
    jira_output: str = Field(
        default="",
        description="Summary of Jira tickets created from PRD requirements.",
    )


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
        (``"openai_pm"``) to their draft content.

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

    # ------------------------------------------------------------------
    # Helper — build available agents
    # ------------------------------------------------------------------
    @staticmethod
    def _get_available_agents() -> dict[str, Agent]:
        """Return a dict of agent-name → Agent for all available LLMs.

        The *default* agent (``DEFAULT_AGENT`` env var, falls back to
        ``openai_pm``) is always created first and is required.

        ``DEFAULT_MULTI_AGENTS`` controls how many PM agents run in
        parallel:

        * **1** (default) — only the default agent is used.
        * **2** — the default agent plus one optional agent whose API
          key is present.
        """
        default = get_default_agent()
        max_agents = int(
            os.environ.get("DEFAULT_MULTI_AGENTS", str(DEFAULT_MULTI_AGENTS)),
        )
        max_agents = max(1, max_agents)  # at least the default

        agents: dict[str, Agent] = {}

        # --- factories keyed by agent identifier ---
        def _openai() -> Agent:
            return create_product_manager()

        def _gemini() -> Agent:
            return create_gemini_product_manager()

        factories: dict[str, tuple[callable, str | list[str] | None]] = {
            AGENT_OPENAI: (_openai, "OPENAI_API_KEY"),
            AGENT_GEMINI: (_gemini, ["GOOGLE_API_KEY", "GOOGLE_CLOUD_PROJECT"]),
        }

        # 1) Create the default agent (required)
        factory_fn, _ = factories[default]
        agents[default] = factory_fn()
        logger.info("[Agents] Default agent: %s", default)

        # 2) Create optional secondary agents (if multi-agent is enabled)
        if len(agents) < max_agents:
            for name, (factory_fn, env_key) in factories.items():
                if name == default:
                    continue  # already created
                if len(agents) >= max_agents:
                    break
                # env_key may be a single string or a list of alternatives
                if env_key:
                    keys = [env_key] if isinstance(env_key, str) else env_key
                    if not any(os.environ.get(k) for k in keys):
                        logger.info("[Agents] None of %s set — skipping %s",
                                    keys, name)
                        continue
                try:
                    agents[name] = factory_fn()
                    logger.info("[Agents] Optional agent enabled: %s", name)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "[Agents] Failed to create %s: %s — continuing without it",
                        name, exc,
                    )
        else:
            logger.info(
                "[Agents] DEFAULT_MULTI_AGENTS=%d — using default agent only",
                max_agents,
            )

        return agents

    # ------------------------------------------------------------------
    # Helper — run multiple agents in parallel for a section draft
    # ------------------------------------------------------------------
    @staticmethod
    def _run_agents_parallel(
        agents: dict[str, Agent],
        task_configs: dict,
        section_title: str,
        idea: str,
        section_content: str,
        executive_summary: str,
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Execute draft tasks across *agents* in parallel.

        Returns a tuple of:
            - ``{agent_name: raw_output}`` dict with successful results.
            - ``{agent_name: error_message}`` dict for agents that failed.

        If one agent fails the others still succeed; the error is logged
        and that agent is omitted from the result dict.
        """
        def _draft(agent_name: str, agent: Agent) -> tuple[str, str]:
            draft_task = Task(
                description=task_configs["draft_section_task"]["description"].format(
                    section_title=section_title,
                    idea=idea,
                    section_content=section_content or "(Initial draft)",
                    executive_summary=executive_summary or "(Not yet available)",
                ),
                expected_output=task_configs["draft_section_task"]["expected_output"].format(
                    section_title=section_title,
                ),
                agent=agent,
            )
            crew = Crew(
                agents=[agent],
                tasks=[draft_task],
                process=Process.sequential,
                verbose=is_verbose(),
            )
            result = crew_kickoff_with_retry(crew, step_label=f"draft_{agent_name}")
            return agent_name, result.raw

        results: dict[str, str] = {}
        failed: dict[str, str] = {}
        if len(agents) == 1:
            # Fast path — no thread overhead for single agent
            name, agent = next(iter(agents.items()))
            _, raw = _draft(name, agent)
            results[name] = raw
        else:
            with ThreadPoolExecutor(max_workers=len(agents)) as pool:
                futures = {
                    pool.submit(_draft, name, agent): name
                    for name, agent in agents.items()
                }
                for future in as_completed(futures):
                    agent_name = futures[future]
                    try:
                        _, raw = future.result()
                        results[agent_name] = raw
                    except Exception as exc:  # noqa: BLE001
                        error_msg = f"{type(exc).__name__}: {exc}"
                        logger.error(
                            "[Draft] Agent '%s' failed: %s — skipping", agent_name, error_msg,
                        )
                        failed[agent_name] = error_msg

        if not results:
            raise RuntimeError("All agents failed during parallel drafting")

        # Reorder so default agent appears first in the dict.
        # as_completed returns results in finishing order which is
        # non-deterministic; callers rely on iteration order to pick
        # the initial selected agent.
        default = get_default_agent()
        if default in results and next(iter(results)) != default:
            results = {default: results[default], **{k: v for k, v in results.items() if k != default}}

        return results, failed

    # ------------------------------------------------------------------
    # Helper — parse approval decision
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_decision(
        decision: ApprovalDecision,
        available_agents: list[str],
    ) -> tuple[str, bool | str]:
        """Normalise an *ApprovalDecision* into ``(agent_name, action)``.

        *action* is ``True`` (approve), ``False`` (self-critique + refine)
        or a ``str`` (user-feedback → refine).
        """
        if isinstance(decision, tuple):
            agent_name, action = decision
            return str(agent_name), action

        # Legacy single-value return — prefer the DEFAULT_AGENT;
        # fall back to the first available agent if it is not in the list.
        default = get_default_agent()
        default_agent = default if default in available_agents else available_agents[0]
        return default_agent, decision

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
            refined, history = refine_idea(
                self.state.idea, run_id=self.state.run_id,
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
    # Step 0c — Requirements Breakdown (Gemini-only, optional)
    # ------------------------------------------------------------------
    def _maybe_breakdown_requirements(self) -> None:
        """Run the Gemini-powered requirements breakdown agent.

        Decomposes the (optionally refined) idea into structured product
        requirements with data entities, state machines, AI augmentation
        points, and API contract sketches.

        Skipped when Gemini credentials are missing or when the
        requirements were already broken down (e.g. resumed run).
        """
        if self.state.requirements_broken_down:
            logger.info(
                "[RequirementsBreakdown] Skipping — already broken down"
            )
            return

        # Only run when Gemini credentials are present
        has_api_key = bool(os.environ.get("GOOGLE_API_KEY"))
        has_project = bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))
        if not has_api_key and not has_project:
            logger.info(
                "[RequirementsBreakdown] Skipping — no GOOGLE_API_KEY "
                "or GOOGLE_CLOUD_PROJECT set"
            )
            return

        logger.info(
            "[RequirementsBreakdown] Breaking down idea into requirements"
        )
        try:
            from crewai_productfeature_planner.agents.requirements_breakdown import (
                breakdown_requirements,
            )

            requirements, history = breakdown_requirements(
                self.state.idea, run_id=self.state.run_id,
            )
            self.state.requirements_breakdown = requirements
            self.state.requirements_broken_down = True
            self.state.breakdown_history = history
            logger.info(
                "[RequirementsBreakdown] Breakdown complete "
                "(%d chars, %d iterations)",
                len(requirements), len(history),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[RequirementsBreakdown] Breakdown failed: %s — "
                "continuing without requirements",
                exc,
            )

    # ------------------------------------------------------------------
    # Step 1 — Executive Summary iteration → then section drafting
    # ------------------------------------------------------------------
    @start()
    def generate_sections(self) -> str:
        """Run the agent pipeline, iterate the executive summary, then draft sections."""
        # ── Agent pipeline (idea refinement → requirements → …) ──
        from crewai_productfeature_planner.orchestrator import (
            build_default_pipeline,
        )

        orchestrator = build_default_pipeline(self)
        orchestrator.run_pipeline()

        agents = self._get_available_agents()
        task_configs = get_task_configs()

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
        skip_phase1 = existing_iters >= exec_resume_threshold

        if skip_phase1:
            logger.info(
                "[Phase 1] Skipping — executive summary already has "
                "%d iteration(s) (threshold=%d). Using last iteration "
                "as context for section drafting.",
                existing_iters,
                exec_resume_threshold,
            )
            # Ensure the executive summary is marked approved
            self.state.executive_summary.is_approved = True
            self.state.finalized_idea = (
                self.state.executive_summary.latest_content
            )
        else:
            # ── Phase 1: Executive Summary iteration ─────────────
            logger.info(
                "[Phase 1] Iterating executive summary for idea: '%s'",
                self.state.idea[:80],
            )
            self._iterate_executive_summary(agents, task_configs)

            # ── User decision gate — continue to sections? ───────
            if self.executive_summary_callback is not None:
                continue_to_sections = self.executive_summary_callback(
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
                        "[Phase 1] User chose not to continue to sections — "
                        "stopping after executive summary"
                    )
                    raise ExecutiveSummaryCompleted()
            else:
                # No callback — auto-continue to sections
                logger.info(
                    "[Phase 1] No executive_summary_callback set — "
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
                    self._section_approval_loop(section, agents, task_configs)
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
                )
            except Exception as exc:
                logger.error("[Draft] Section '%s' generation failed: %s",
                             section.title, exc)
                save_failed(
                    run_id=self.state.run_id,
                    idea=self.state.idea,
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
                idea=self.state.idea,
                iteration=section.iteration,
                draft={section.key: section.content},
                step=f"draft_{section.key}",
                section_key=section.key,
                section_title=section.title,
                agent_results=agent_results,
            )

            logger.info("[Draft] Step %d/%d — Section '%s' generated (%d chars, %d agent(s))",
                        section.step, total_steps, section.title,
                        len(section.content), len(agent_results))

            # --- Section approval loop ---
            self._section_approval_loop(section, agents, task_configs)

        logger.info("[Steps 1-3] All sections completed, total iterations=%d",
                    self.state.iteration)
        return self.finalize()

    # ------------------------------------------------------------------
    # Phase 1 helper — Executive Summary iteration
    # ------------------------------------------------------------------
    def _iterate_executive_summary(
        self,
        agents: dict[str, Agent],
        task_configs: dict,
    ) -> None:
        """Draft and iterate the executive summary using critique_prd_task.

        Uses ``draft_prd_task`` for the initial draft, then loops
        ``critique_prd_task`` up to min/max iterations.  Each iteration
        both critiques the current summary and produces a refined version.

        The executive summary is stored at the top-level
        ``executive_summary`` array in ``workingIdeas`` (not under ``draft``).
        """
        min_iter, max_iter = _get_section_iteration_limits()
        # Pick the default agent for the executive summary phase
        default_name = get_default_agent()
        pm = agents.get(default_name) or next(iter(agents.values()))

        # Always persist the original user-inputted idea, not the refined one
        user_idea = self.state.original_idea or self.state.idea

        # ── Initial draft (iteration 1) ───────────────────────
        draft_task = Task(
            description=task_configs["draft_prd_task"]["description"].format(
                idea=self.state.idea,
                executive_summary="(initial draft — first iteration)",
            ),
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
                run_id=self.state.run_id,
                idea=user_idea,
                iteration=0,
                error=str(exc),
                step="draft_executive_summary",
            )
            raise

        current_content = draft_result.raw
        now = datetime.now(timezone.utc).isoformat()
        first_iter = ExecutiveSummaryIteration(
            content=current_content,
            iteration=1,
            critique=None,
            updated_date=now,
        )
        self.state.executive_summary.iterations.append(first_iter)
        self.state.iteration = 1
        self.state.update_date = now

        save_executive_summary(
            run_id=self.state.run_id,
            idea=user_idea,
            iteration=1,
            content=current_content,
            critique=None,
        )
        logger.info(
            "[ExecSummary] Initial draft (%d chars)", len(current_content),
        )

        # ── Critique → iterate loop ──────────────────────────
        iteration = 1
        while iteration < max_iter:
            # --- Critique ---
            logger.info(
                "[ExecSummary] Critique iteration %d/%d", iteration, max_iter,
            )
            critique_task = Task(
                description=task_configs["critique_prd_task"]["description"].format(
                    critique="(generate critique)",
                    executive_summary=current_content,
                ),
                expected_output=task_configs["critique_prd_task"][
                    "expected_output"
                ],
                agent=pm,
            )
            crew = Crew(
                agents=[pm],
                tasks=[critique_task],
                process=Process.sequential,
                verbose=is_verbose(),
            )
            try:
                critique_result = crew_kickoff_with_retry(
                    crew, step_label=f"critique_exec_summary_iter{iteration}",
                )
            except Exception as exc:
                logger.error(
                    "[ExecSummary] Critique failed at iteration %d: %s",
                    iteration, exc,
                )
                save_failed(
                    run_id=self.state.run_id,
                    idea=user_idea,
                    iteration=iteration,
                    error=str(exc),
                    step=f"critique_exec_summary_iter{iteration}",
                )
                raise

            critique_text = critique_result.raw

            # Update critique on the current iteration record
            update_executive_summary_critique(
                run_id=self.state.run_id,
                iteration=iteration,
                critique=critique_text,
            )
            # Update in-memory model
            current_iter = self.state.executive_summary.iterations[-1]
            current_iter.critique = critique_text
            self.state.critique = critique_text

            # --- Check termination ----
            is_ready = "READY_FOR_DEV" in critique_text.upper()
            past_min = iteration >= min_iter

            if is_ready and past_min:
                logger.info(
                    "[ExecSummary] READY_FOR_DEV at iteration %d "
                    "(min=%d) — approved",
                    iteration, min_iter,
                )
                self.state.executive_summary.is_approved = True
                break

            # --- Produce refined version (the critique task output
            #     already contains the refined executive summary per
            #     the task description; but we run the draft task
            #     again with the critique as context to get a clean
            #     refined version) ---
            iteration += 1
            refine_desc = task_configs["draft_prd_task"]["description"].format(
                idea=self.state.idea,
                executive_summary=current_content,
            )
            refine_desc += (
                f"\n\n--- CRITIQUE FEEDBACK ---\n{critique_text}\n"
                f"--- END OF CRITIQUE ---\n\n"
                "Address every gap identified in the critique above. "
                "Produce an improved executive summary."
            )
            refine_task = Task(
                description=refine_desc,
                expected_output=task_configs["draft_prd_task"][
                    "expected_output"
                ],
                agent=pm,
            )
            crew = Crew(
                agents=[pm],
                tasks=[refine_task],
                process=Process.sequential,
                verbose=is_verbose(),
            )
            try:
                refine_result = crew_kickoff_with_retry(
                    crew,
                    step_label=f"refine_exec_summary_iter{iteration}",
                )
            except Exception as exc:
                logger.error(
                    "[ExecSummary] Refine failed at iteration %d: %s",
                    iteration, exc,
                )
                save_failed(
                    run_id=self.state.run_id,
                    idea=user_idea,
                    iteration=iteration,
                    error=str(exc),
                    step=f"refine_exec_summary_iter{iteration}",
                )
                raise

            current_content = refine_result.raw
            now = datetime.now(timezone.utc).isoformat()
            new_iter = ExecutiveSummaryIteration(
                content=current_content,
                iteration=iteration,
                critique=None,
                updated_date=now,
            )
            self.state.executive_summary.iterations.append(new_iter)
            self.state.iteration = iteration
            self.state.update_date = now

            save_executive_summary(
                run_id=self.state.run_id,
                idea=user_idea,
                iteration=iteration,
                content=current_content,
                critique=None,
            )
            logger.info(
                "[ExecSummary] Refined iteration %d (%d chars)",
                iteration, len(current_content),
            )

        # Force-approve if max reached without READY_FOR_DEV
        if not self.state.executive_summary.is_approved:
            self.state.executive_summary.is_approved = True
            logger.info(
                "[ExecSummary] Max iterations (%d) reached — "
                "force-approved",
                max_iter,
            )

        # Copy the last iterated executive summary to finalized_idea
        self.state.finalized_idea = self.state.executive_summary.latest_content
        save_finalized_idea(
            run_id=self.state.run_id,
            finalized_idea=self.state.finalized_idea,
        )
        logger.info(
            "[ExecSummary] Copied executive summary to finalized_idea "
            "(%d chars)",
            len(self.state.finalized_idea),
        )

    def _section_approval_loop(self, section, agents: dict[str, Agent], task_configs) -> None:
        """Iterate a single section through critique→refine cycles.

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
        total_steps = len(self.state.draft.sections)

        while not section.is_approved:
            user_feedback: str | None = None
            available = list(section.agent_results.keys()) or list(agents.keys())

            # ── Optional user gate (callback) ─────────────────
            if self.approval_callback is not None:
                decision = self.approval_callback(
                    section.iteration,
                    section.key,
                    section.agent_results,
                    self.state.draft,
                    active_agents=list(self.state.active_agents),
                    dropped_agents=list(self.state.dropped_agents),
                    agent_errors=dict(self.state.agent_errors),
                    original_idea=self.state.original_idea,
                    idea_refined=self.state.idea_refined,
                )

                agent_name, action = self._parse_decision(decision, available)

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

            # Resolve agent for critique / refine
            selected = section.selected_agent or available[0]
            pm = agents.get(selected) or next(iter(agents.values()))

            # ── Critique (user feedback or agent) ─────────────
            if user_feedback is not None:
                self.state.critique = user_feedback
                section.critique = user_feedback
            else:
                logger.info(
                    "[Critique] Step %d/%d — Section '%s' — iteration %d",
                    section.step, total_steps, section.title,
                    section.iteration,
                )
                critique_task = Task(
                    description=task_configs["critique_section_task"][
                        "description"
                    ].format(
                        section_title=section.title,
                        critique_section_content=section.content,
                        executive_summary=self.state.executive_summary.latest_content or "(Not yet available)",
                        approved_sections=self.state.draft.approved_context(exclude_key=section.key) or "(None yet)",
                    ),
                    expected_output=task_configs["critique_section_task"][
                        "expected_output"
                    ],
                    agent=pm,
                )
                crew = Crew(
                    agents=[pm],
                    tasks=[critique_task],
                    process=Process.sequential,
                    verbose=is_verbose(),
                )
                try:
                    critique_result = crew_kickoff_with_retry(
                        crew, step_label=f"critique_{section.key}",
                    )
                except Exception as exc:
                    logger.error(
                        "[Critique] Section '%s' failed at iteration %d: %s",
                        section.title, section.iteration, exc,
                    )
                    save_failed(
                        run_id=self.state.run_id,
                        idea=self.state.idea,
                        iteration=self.state.iteration,
                        error=str(exc),
                        draft={section.key: section.content},
                        step=f"critique_{section.key}",
                        section_key=section.key,
                        section_title=section.title,
                    )
                    raise
                self.state.critique = critique_result.raw
                section.critique = self.state.critique

            update_section_critique(
                run_id=self.state.run_id,
                section_key=section.key,
                iteration=section.iteration,
                critique=self.state.critique,
            )

            # ── Check termination conditions ──────────────────
            is_ready = "SECTION_READY" in self.state.critique.upper()
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

            if is_ready and past_min and self.approval_callback is None:
                section.is_approved = True
                logger.info(
                    "[Critique] Section '%s' marked SECTION_READY at "
                    "iteration %d (min=%d) — auto-approved",
                    section.title, section.iteration, min_iter,
                )
                break

            # ── Refine ────────────────────────────────────────
            prev_content = section.content  # snapshot for degenerate guard
            logger.info(
                "[Refine] Step %d/%d — Section '%s' — iteration %d",
                section.step, total_steps, section.title,
                section.iteration,
            )
            refine_task = Task(
                description=task_configs["refine_section_task"][
                    "description"
                ].format(
                    section_title=section.title,
                    section_content=section.content,
                    critique_section_content=self.state.critique,
                    executive_summary=self.state.executive_summary.latest_content or "(Not yet available)",
                    approved_sections=self.state.draft.approved_context(exclude_key=section.key) or "(None yet)",
                ),
                expected_output=task_configs["refine_section_task"][
                    "expected_output"
                ].format(
                    section_title=section.title,
                    critique_section_content=self.state.critique,
                ),
                agent=pm,
            )
            crew = Crew(
                agents=[pm],
                tasks=[refine_task],
                process=Process.sequential,
                verbose=is_verbose(),
            )
            try:
                refine_result = crew_kickoff_with_retry(
                    crew, step_label=f"refine_{section.key}",
                )
            except Exception as exc:
                logger.error(
                    "[Refine] Section '%s' failed at iteration %d: %s",
                    section.title, section.iteration, exc,
                )
                save_failed(
                    run_id=self.state.run_id,
                    idea=self.state.idea,
                    iteration=self.state.iteration,
                    error=str(exc),
                    draft={section.key: section.content},
                    step=f"refine_{section.key}",
                    section_key=section.key,
                    section_title=section.title,
                )
                raise
            section.content = refine_result.raw

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
                self.state.iteration += 1
                self.state.update_date = section.updated_date
                continue

            # Update agent_results so subsequent callbacks see refined content
            section.agent_results = {section.selected_agent: section.content}
            section.iteration += 1
            section.updated_date = datetime.now(timezone.utc).isoformat()
            self.state.iteration += 1
            self.state.update_date = section.updated_date

            save_iteration(
                run_id=self.state.run_id,
                idea=self.state.idea,
                iteration=section.iteration,
                draft={section.key: section.content},
                critique=self.state.critique,
                step=f"refine_{section.key}",
                section_key=section.key,
                section_title=section.title,
                selected_agent=section.selected_agent,
            )

            logger.debug(
                "[Refine] Section '%s' refined (%d chars)",
                section.title, len(section.content),
            )

    # ------------------------------------------------------------------
    # Save progress markdown (partial output on error / pause)
    # ------------------------------------------------------------------
    def save_progress(self) -> str:
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
        idea_text = self.state.finalized_idea or self.state.idea
        if idea_text:
            parts.append(f"## Refined Idea\n\n{idea_text}")

        # Requirements breakdown
        if self.state.requirements_broken_down and self.state.requirements_breakdown:
            parts.append(f"## Requirements Breakdown\n\n{self.state.requirements_breakdown}")

        # Executive summary (latest iteration)
        if self.state.executive_summary.latest_content:
            parts.append(f"## Executive Summary\n\n{self.state.executive_summary.latest_content}")

        # Any drafted sections (skip executive_summary — already above)
        for section in self.state.draft.sections:
            if section.content and section.key != "executive_summary":
                parts.append(f"## {section.title}\n\n{section.content}")

        if not parts:
            logger.info("[Progress] Nothing to save — no content produced yet")
            return ""

        # Use the definitive header when every section is approved;
        # otherwise mark the document as in-progress.
        all_approved = self.state.draft.all_approved()
        header = (
            "# Product Requirements Document\n\n"
            if all_approved
            else "# Product Requirements Document (In Progress)\n\n"
        )
        content = header + "\n\n---\n\n".join(parts)

        writer = PRDFileWriteTool()
        save_result = writer._run(
            content=content,
            filename="",
            version=max(self.state.iteration, 1),
        )
        logger.info("[Progress] %s", save_result)

        # Persist the output file path to the workingIdeas document
        self._persist_output_path(save_result)

        # Update workingIdeas status from "failed" → "paused" so a
        # subsequent restart treats this as a resumable run.
        mark_paused(self.state.run_id)

        return save_result

    def _persist_output_path(self, save_result: str) -> None:
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
        old_path = get_output_file(self.state.run_id)
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

        save_output_file(self.state.run_id, output_path)

    # ------------------------------------------------------------------
    # Step 4 — Final Assembly & Persist
    # ------------------------------------------------------------------
    def finalize(self) -> str:
        """Assemble the final PRD from all approved sections and persist."""
        logger.info("[Step 4] Finalising PRD (total iterations=%d)", self.state.iteration)
        self.state.final_prd = self.state.draft.assemble()

        # Save Markdown to file
        writer = PRDFileWriteTool()
        save_result = writer._run(
            content=self.state.final_prd,
            filename="",
            version=self.state.iteration,
        )

        # Persist the output file path to the workingIdeas document
        self._persist_output_path(save_result)

        # Convert to Confluence-compatible XHTML
        confluence_xhtml = md_to_confluence_xhtml(self.state.final_prd)
        logger.info(
            "[Step 4] Generated Confluence XHTML (%d chars)", len(confluence_xhtml)
        )

        # Mark working-idea document as completed
        mark_completed(self.state.run_id)

        self.state.is_ready = True
        self.state.status = "completed"
        self.state.completed_at = datetime.now(timezone.utc).isoformat()
        self.state.update_date = self.state.completed_at
        logger.info("[Step 4] %s", save_result)

        # ── Post-completion: Confluence publish & Jira ticketing ──
        self._run_post_completion()

        return save_result

    # ------------------------------------------------------------------
    # Post-completion pipeline (Confluence + Jira)
    # ------------------------------------------------------------------
    def _run_post_completion(self) -> None:
        """Run the Atlassian publishing pipeline after PRD finalization.

        Publishes the completed PRD to Confluence and creates Jira
        tickets.  Failures are logged but do not fail the overall flow.
        """
        try:
            from crewai_productfeature_planner.orchestrator import (
                build_post_completion_pipeline,
            )

            pipeline = build_post_completion_pipeline(self)
            pipeline.run_pipeline()
        except Exception as exc:
            logger.warning(
                "[PostCompletion] Atlassian pipeline failed — "
                "PRD is saved but not published: %s",
                exc,
            )
