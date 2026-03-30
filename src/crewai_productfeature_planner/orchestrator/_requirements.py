"""Requirements Breakdown stage factory.

Wraps the ``requirements_breakdown`` agent in an :class:`AgentStage`
that reads/writes the :class:`PRDFlow` state.
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
        from crewai_productfeature_planner.scripts.memory_loader import (
            resolve_project_id,
        )

        logger.info(
            "[RequirementsBreakdown] Breaking down idea into requirements"
        )
        project_id = resolve_project_id(flow.state.run_id)
        requirements, history = breakdown_requirements(
            flow.state.idea,
            run_id=flow.state.run_id,
            original_idea=flow.state.original_idea,
            project_id=project_id,
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
        # On resume: if section content already exists, the user
        # previously approved requirements — skip the gate so they
        # aren't re-prompted.
        if any(s.content for s in flow.state.draft.sections):
            logger.info(
                "[RequirementsBreakdown] Auto-approving — sections "
                "already in progress (resumed run)",
            )
            return False
        # If specialist agents already produced output (CEO review,
        # Eng Plan, or UX Design), the user already passed the
        # requirements gate in a prior run attempt.
        if (
            flow.state.executive_product_summary
            or flow.state.engineering_plan
            or flow.state.ux_design_status
        ):
            logger.info(
                "[RequirementsBreakdown] Auto-approving — specialist "
                "agents already ran (resumed run; eps=%s, eng=%s, ux=%s)",
                bool(flow.state.executive_product_summary),
                bool(flow.state.engineering_plan),
                flow.state.ux_design_status or "(none)",
            )
            return False
        return (
            flow.state.requirements_broken_down
            and flow._resolve_callback("requirements_approval_callback") is not None
        )

    def _get_approval() -> bool:
        cb = flow._resolve_callback("requirements_approval_callback")
        return cb(
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
