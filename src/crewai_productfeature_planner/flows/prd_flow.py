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
The assembled final PRD is saved to ``ideas.finalizeIdeas``.
"""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Union

from crewai import Agent, Crew, Process, Task
from crewai.flow.flow import Flow, start
from pydantic import BaseModel, Field

from crewai_productfeature_planner.agents.product_manager import (
    create_product_manager,
    get_task_configs,
)
from crewai_productfeature_planner.apis.prd.models import (
    AGENT_GEMINI,
    AGENT_OPENAI,
    PRDDraft,
    get_default_agent,
)
from crewai_productfeature_planner.scripts.confluence_xhtml import md_to_confluence_xhtml
from crewai_productfeature_planner.scripts.logging_config import get_logger
from crewai_productfeature_planner.mongodb import mark_completed, save_failed, save_finalized, save_iteration
from crewai_productfeature_planner.scripts.retry import crew_kickoff_with_retry
from crewai_productfeature_planner.tools.file_write_tool import PRDFileWriteTool

logger = get_logger(__name__)

PAUSE_SENTINEL = "__PAUSE__"

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

    The idea has already been saved to ``finalizeIdeas`` and the working
    idea marked as completed by the time this is raised.
    """


class RequirementsFinalized(Exception):
    """Raised when the user finalizes the requirements breakdown without PRD.

    The requirements have been saved to ``finalizeIdeas`` and the
    working idea marked as completed by the time this is raised.
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


class PRDFlow(Flow[PRDState]):
    """CrewAI Flow that drafts, critiques, and refines a PRD section by section.

    The flow processes sections in a fixed order, starting with Executive
    Summary.  Each approved section is used as context for subsequent ones.

    When ``GOOGLE_API_KEY`` or ``GOOGLE_CLOUD_PROJECT`` is set in the
    environment, the flow creates a second *Gemini Product Manager* agent
    and runs both agents in parallel for the initial draft.  The user
    then picks which result to keep.

    Args:
        approval_callback: An optional callable::

            (iteration, section_key, agent_results, draft) -> ApprovalDecision

        *agent_results* is ``dict[str, str]`` mapping agent names
        (``"openai_pm"``, ``"gemini_pm"``) to their draft content.

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

    # ------------------------------------------------------------------
    # Helper — build available agents
    # ------------------------------------------------------------------
    @staticmethod
    def _get_available_agents() -> dict[str, Agent]:
        """Return a dict of agent-name → Agent for all available LLMs.

        The *default* agent (``DEFAULT_AGENT`` env var, falls back to
        ``openai_pm``) is always created first and is required.  Any
        additional agents whose API key is present are appended as
        optional parallel runners.
        """
        default = get_default_agent()
        agents: dict[str, Agent] = {}

        # --- factories keyed by agent identifier ---
        def _openai() -> Agent:
            return create_product_manager()

        def _gemini() -> Agent:
            from crewai_productfeature_planner.agents.gemini_product_manager import (
                create_gemini_product_manager,
            )
            return create_gemini_product_manager()

        factories: dict[str, tuple[callable, str | list[str] | None]] = {
            AGENT_OPENAI: (_openai, "OPENAI_API_KEY"),
            AGENT_GEMINI: (_gemini, ["GOOGLE_API_KEY", "GOOGLE_CLOUD_PROJECT"]),
        }

        # 1) Create the default agent (required)
        factory_fn, _ = factories[default]
        agents[default] = factory_fn()
        logger.info("[Agents] Default agent: %s", default)

        # 2) Create optional secondary agents
        for name, (factory_fn, env_key) in factories.items():
            if name == default:
                continue  # already created
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
        context: str,
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
                    context_sections=context or "(No other sections yet)",
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
                verbose=True,
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

        # Legacy single-value return — pick first available agent
        default_agent = available_agents[0]
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
    # Step 1 — Generate sections one by one
    # ------------------------------------------------------------------
    @start()
    def generate_sections(self) -> str:
        """Run the agent pipeline then draft each section."""
        # ── Agent pipeline (idea refinement → requirements → …) ──
        from crewai_productfeature_planner.orchestrator import (
            build_default_pipeline,
        )

        orchestrator = build_default_pipeline(self)
        orchestrator.run_pipeline()

        logger.info("[Step 1] Generating PRD sections for idea: '%s'",
                    self.state.idea[:80])
        agents = self._get_available_agents()
        task_configs = get_task_configs()

        # Track initial agent roster
        self.state.active_agents = list(agents.keys())
        self.state.dropped_agents = []

        for section in self.state.draft.sections:
            self.state.current_section_key = section.key
            total_steps = len(self.state.draft.sections)
            context = self.state.draft.all_sections_context(exclude_key=section.key)

            logger.info("[Draft] Step %d/%d — Generating section '%s' with %d agent(s)",
                        section.step, total_steps, section.title, len(agents))

            # --- Parallel agent drafting ---
            try:
                agent_results, failed_agents = self._run_agents_parallel(
                    agents=agents,
                    task_configs=task_configs,
                    section_title=section.title,
                    idea=self.state.idea,
                    context=context,
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
            # Default content to first available agent's result
            first_agent = next(iter(agent_results))
            section.content = agent_results[first_agent]
            section.selected_agent = first_agent
            section.iteration = 1
            self.state.iteration += 1

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
                iteration=self.state.iteration,
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

    def _section_approval_loop(self, section, agents: dict[str, Agent], task_configs) -> None:
        """Critique/refine a single section until user approves it."""
        while not section.is_approved:
            user_feedback: str | None = None
            available = list(section.agent_results.keys()) or list(agents.keys())

            # --- User approval gate ---
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
                    logger.info("[Approval] Step %d/%d — Section '%s' approved (agent=%s) at iteration %d",
                                section.step, len(self.state.draft.sections),
                                section.title, agent_name, section.iteration)
                    break
                if action == PAUSE_SENTINEL or decision == PAUSE_SENTINEL:
                    logger.info("[Pause] User requested pause at step %d/%d section '%s' iteration %d",
                                section.step, len(self.state.draft.sections),
                                section.title, section.iteration)
                    raise PauseRequested()
                if isinstance(action, str) and action.strip():
                    user_feedback = action.strip()
                    logger.info(
                        "[Approval] User provided critique for section '%s' (agent=%s, %d chars)",
                        section.title, agent_name, len(user_feedback),
                    )

            # Resolve the agent to use for critique/refine
            selected = section.selected_agent or available[0]
            pm = agents.get(selected) or next(iter(agents.values()))

            # --- Self-Critique (skipped when user provided feedback) ---
            context = self.state.draft.all_sections_context(exclude_key=section.key)

            if user_feedback is not None:
                self.state.critique = user_feedback
                save_iteration(
                    run_id=self.state.run_id,
                    idea=self.state.idea,
                    iteration=self.state.iteration,
                    draft={section.key: section.content},
                    critique=self.state.critique,
                    step=f"user_critique_{section.key}",
                    section_key=section.key,
                    section_title=section.title,
                )
            else:
                logger.info("[Critique] Step %d/%d — Section '%s' — iteration %d",
                            section.step, len(self.state.draft.sections),
                            section.title, section.iteration)
                critique_task = Task(
                    description=task_configs["critique_section_task"]["description"].format(
                        section_title=section.title,
                        section_content=section.content,
                        context_sections=context or "(No other sections available)",
                    ),
                    expected_output=task_configs["critique_section_task"]["expected_output"],
                    agent=pm,
                )
                crew = Crew(
                    agents=[pm],
                    tasks=[critique_task],
                    process=Process.sequential,
                    verbose=True,
                )
                try:
                    critique_result = crew_kickoff_with_retry(
                        crew, step_label=f"critique_{section.key}",
                    )
                except Exception as exc:
                    logger.error("[Critique] Section '%s' failed at iteration %d: %s",
                                 section.title, section.iteration, exc)
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

                save_iteration(
                    run_id=self.state.run_id,
                    idea=self.state.idea,
                    iteration=self.state.iteration,
                    draft={section.key: section.content},
                    critique=self.state.critique,
                    step=f"critique_{section.key}",
                    section_key=section.key,
                    section_title=section.title,
                )

                # Auto-approval fallback
                if "SECTION_READY" in self.state.critique.upper() and self.approval_callback is None:
                    section.is_approved = True
                    logger.info("[Critique] Section '%s' marked SECTION_READY — auto-approved",
                                section.title)
                    break

            # --- Refinement ---
            logger.info("[Refine] Step %d/%d — Section '%s' — iteration %d",
                        section.step, len(self.state.draft.sections),
                        section.title, section.iteration)
            refine_task = Task(
                description=task_configs["refine_section_task"]["description"].format(
                    section_title=section.title,
                    section_content=section.content,
                    critique=self.state.critique,
                    context_sections=context or "(No other sections available)",
                ),
                expected_output=task_configs["refine_section_task"]["expected_output"].format(
                    section_title=section.title,
                ),
                agent=pm,
            )
            crew = Crew(
                agents=[pm],
                tasks=[refine_task],
                process=Process.sequential,
                verbose=True,
            )
            try:
                refine_result = crew_kickoff_with_retry(
                    crew, step_label=f"refine_{section.key}",
                )
            except Exception as exc:
                logger.error("[Refine] Section '%s' failed at iteration %d: %s",
                             section.title, section.iteration, exc)
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
            # Update agent_results so subsequent callbacks see the refined content
            section.agent_results = {section.selected_agent: section.content}
            section.iteration += 1
            self.state.iteration += 1

            save_iteration(
                run_id=self.state.run_id,
                idea=self.state.idea,
                iteration=self.state.iteration,
                draft={section.key: section.content},
                critique=self.state.critique,
                step=f"refine_{section.key}",
                section_key=section.key,
                section_title=section.title,
                selected_agent=section.selected_agent,
            )

            logger.debug("[Refine] Section '%s' refined (%d chars)",
                         section.title, len(section.content))

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

        # Convert to Confluence-compatible XHTML
        confluence_xhtml = md_to_confluence_xhtml(self.state.final_prd)
        logger.info(
            "[Step 4] Generated Confluence XHTML (%d chars)", len(confluence_xhtml)
        )

        # Save to MongoDB finalizeIdeas (Markdown + XHTML)
        doc_id = save_finalized(
            run_id=self.state.run_id,
            idea=self.state.idea,
            iteration=self.state.iteration,
            final_prd=self.state.final_prd,
            confluence_xhtml=confluence_xhtml,
        )
        if doc_id is None:
            logger.error(
                "[Step 4] save_finalized returned None for run_id=%s — "
                "the PRD may not be persisted in finalizeIdeas",
                self.state.run_id,
            )

        # Mark working-idea documents as completed
        mark_completed(self.state.run_id)

        self.state.is_ready = True
        logger.info("[Step 4] %s", save_result)
        return save_result
