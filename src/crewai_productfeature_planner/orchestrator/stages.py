"""Stage factory functions for the agent pipeline.

Each ``build_*_stage(flow)`` function creates an :class:`AgentStage`
whose callables close over the given *flow* instance so they can
read/write ``flow.state`` and ``flow.<callback>`` attributes.

To extend the pipeline with a new agent, add a new factory here and
register it inside :func:`build_default_pipeline`.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from crewai_productfeature_planner.orchestrator.orchestrator import (
    AgentOrchestrator,
    AgentStage,
    StageResult,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

if TYPE_CHECKING:
    from crewai_productfeature_planner.flows.prd_flow import PRDFlow

logger = get_logger(__name__)


# ── helpers ───────────────────────────────────────────────────────────


def _has_gemini_credentials() -> bool:
    """Return True when at least one Gemini auth mechanism is configured."""
    return bool(
        os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
    )


# ── Stage 1 — Idea Refinement ────────────────────────────────────────


def build_idea_refinement_stage(flow: "PRDFlow") -> AgentStage:
    """Create an :class:`AgentStage` that refines the raw idea.

    The stage wraps :func:`refine_idea` from the ``idea_refiner``
    agent and maps its output onto ``flow.state``.
    """

    def _should_skip() -> bool:
        if flow.state.idea_refined:
            logger.info("[IdeaRefiner] Skipping — idea already refined")
            return True
        if not _has_gemini_credentials():
            logger.info(
                "[IdeaRefiner] Skipping — no GOOGLE_API_KEY "
                "or GOOGLE_CLOUD_PROJECT set"
            )
            return True
        return False

    def _run() -> StageResult:
        from crewai_productfeature_planner.agents.idea_refiner import (
            refine_idea,
        )

        logger.info("[IdeaRefiner] Refining idea before PRD generation")
        # Snapshot original idea *before* refinement
        flow.state.original_idea = flow.state.idea
        refined, history = refine_idea(
            flow.state.idea, run_id=flow.state.run_id,
        )
        logger.info(
            "[IdeaRefiner] Idea refined (%d → %d chars, %d iterations)",
            len(flow.state.original_idea), len(refined), len(history),
        )
        return StageResult(output=refined, history=history)

    def _apply(result: StageResult) -> None:
        flow.state.idea = result.output
        flow.state.idea_refined = True
        flow.state.refinement_history = result.history

    def _requires_approval() -> bool:
        return (
            flow.state.idea_refined
            and flow.idea_approval_callback is not None
        )

    def _get_approval() -> bool:
        return flow.idea_approval_callback(
            flow.state.idea,
            flow.state.original_idea,
            flow.state.run_id,
            flow.state.refinement_history,
        )

    from crewai_productfeature_planner.flows.prd_flow import IdeaFinalized

    return AgentStage(
        name="idea_refinement",
        description="Iteratively refine raw idea via industry-expert feedback",
        run=_run,
        should_skip=_should_skip,
        apply=_apply,
        get_approval=_get_approval,
        finalized_exc=IdeaFinalized,
        requires_approval=_requires_approval,
    )


# ── Stage 2 — Requirements Breakdown ─────────────────────────────────


def build_requirements_breakdown_stage(flow: "PRDFlow") -> AgentStage:
    """Create an :class:`AgentStage` that decomposes the idea into
    structured product requirements.

    The stage wraps :func:`breakdown_requirements` from the
    ``requirements_breakdown`` agent.
    """

    def _should_skip() -> bool:
        if flow.state.requirements_broken_down:
            logger.info(
                "[RequirementsBreakdown] Skipping — already broken down"
            )
            return True
        if not _has_gemini_credentials():
            logger.info(
                "[RequirementsBreakdown] Skipping — no GOOGLE_API_KEY "
                "or GOOGLE_CLOUD_PROJECT set"
            )
            return True
        return False

    def _run() -> StageResult:
        from crewai_productfeature_planner.agents.requirements_breakdown import (
            breakdown_requirements,
        )

        logger.info(
            "[RequirementsBreakdown] Breaking down idea into requirements"
        )
        requirements, history = breakdown_requirements(
            flow.state.idea, run_id=flow.state.run_id,
        )
        logger.info(
            "[RequirementsBreakdown] Breakdown complete "
            "(%d chars, %d iterations)",
            len(requirements), len(history),
        )
        return StageResult(output=requirements, history=history)

    def _apply(result: StageResult) -> None:
        flow.state.requirements_breakdown = result.output
        flow.state.breakdown_history = result.history
        flow.state.requirements_broken_down = True

    def _requires_approval() -> bool:
        return (
            flow.state.requirements_broken_down
            and flow.requirements_approval_callback is not None
        )

    def _get_approval() -> bool:
        return flow.requirements_approval_callback(
            flow.state.requirements_breakdown,
            flow.state.idea,
            flow.state.run_id,
            flow.state.breakdown_history,
        )

    from crewai_productfeature_planner.flows.prd_flow import RequirementsFinalized

    return AgentStage(
        name="requirements_breakdown",
        description="Decompose refined idea into detailed product requirements",
        run=_run,
        should_skip=_should_skip,
        apply=_apply,
        get_approval=_get_approval,
        finalized_exc=RequirementsFinalized,
        requires_approval=_requires_approval,
    )


# ── Pipeline assembly ────────────────────────────────────────────────


def build_default_pipeline(flow: "PRDFlow") -> AgentOrchestrator:
    """Assemble the default agent pipeline for PRD generation.

    Current chain::

        1. Idea Refinement   — auto-iterates until idea is polished
        2. Requirements Breakdown — decomposes idea into product requirements
        (… more stages to come)

    To extend, create a new ``build_*_stage`` factory and register it
    here at the desired position.

    Args:
        flow: The :class:`PRDFlow` instance whose state will be read
              and updated by each stage.

    Returns:
        A fully-configured :class:`AgentOrchestrator` ready for
        :meth:`~AgentOrchestrator.run_pipeline`.
    """
    orchestrator = AgentOrchestrator()
    orchestrator.register(build_idea_refinement_stage(flow))
    orchestrator.register(build_requirements_breakdown_stage(flow))
    return orchestrator
