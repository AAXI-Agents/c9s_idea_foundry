"""Idea Refinement stage factory.

Wraps the ``idea_refiner`` agent in an :class:`AgentStage` that
reads/writes the :class:`PRDFlow` state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from crewai_productfeature_planner.orchestrator._helpers import (
    _has_gemini_credentials,
    logger,
)
from crewai_productfeature_planner.orchestrator.orchestrator import (
    AgentStage,
    StageResult,
)

if TYPE_CHECKING:
    from crewai_productfeature_planner.flows.prd_flow import PRDFlow


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
        from crewai_productfeature_planner.scripts.memory_loader import (
            resolve_project_id,
        )

        logger.info("[IdeaRefiner] Refining idea before PRD generation")
        # Snapshot original idea *before* refinement
        flow.state.original_idea = flow.state.idea
        project_id = resolve_project_id(flow.state.run_id)

        # Resolve options callback from the flow if available
        options_cb = getattr(flow, "_idea_options_callback", None)

        refined, history, options_history = refine_idea(
            flow.state.idea,
            run_id=flow.state.run_id,
            project_id=project_id,
            options_callback=options_cb,
        )
        logger.info(
            "[IdeaRefiner] Idea refined (%d → %d chars, %d iterations, "
            "%d option presentations)",
            len(flow.state.original_idea), len(refined), len(history),
            len(options_history),
        )
        return StageResult(
            output=refined, history=history,
            extra={"options_history": options_history},
        )

    def _apply(result: StageResult) -> None:
        flow.state.idea = result.output
        flow.state.idea_refined = True
        flow.state.refinement_history = result.history
        flow.state.refinement_options_history = (
            result.extra.get("options_history", [])
            if result.extra else []
        )

    def _requires_approval() -> bool:
        # Skip the idea approval gate when requirements breakdown is
        # configured (will run next OR has already completed).
        # The user will approve at the requirements stage instead.
        if _has_gemini_credentials():
            logger.info(
                "[IdeaRefiner] Auto-approving — requirements breakdown "
                "%s",
                "already done" if flow.state.requirements_broken_down
                else "will run next",
            )
            return False
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
