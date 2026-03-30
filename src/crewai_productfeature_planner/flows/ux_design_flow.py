"""Standalone UX Design Flow — triggered after PRD completion.

Orchestrates the two-phase UX design pipeline:

1. **Phase 1** — UX Designer + Design Partner → initial draft
2. **Phase 2** — Senior Designer 7-pass review → final design

Triggered by the engagement manager when a PRD is fully completed
with all sections and ready for Confluence publication.

Only two output files are produced per product idea:
- ``ux_design_draft.md``  — overwritten on each draft iteration
- ``ux_design_final.md``  — produced once after Senior Designer review
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from crewai_productfeature_planner.flows._ux_design import (
    run_ux_design_draft,
    run_ux_design_flow,
    run_ux_design_review,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

if TYPE_CHECKING:
    from crewai_productfeature_planner.flows.prd_flow import PRDFlow

logger = get_logger(__name__)


def kick_off_ux_design_flow(
    flow: PRDFlow,
    *,
    progress_callback=None,
) -> str:
    """Entry point for the standalone UX design flow.

    Typically called from ``_finalization.run_post_completion()``
    after the PRD is finalized, or from Slack handlers when the user
    explicitly triggers UX design generation.

    Parameters
    ----------
    flow:
        A PRDFlow instance with populated state (run_id, idea,
        executive_product_summary, requirements_breakdown).
    progress_callback:
        Optional callable for Slack progress updates.

    Returns
    -------
    str
        The UX design content if available, otherwise empty string.
    """
    if progress_callback is not None:
        flow._progress_callback = progress_callback

    logger.info(
        "[UXDesignFlow] Kicking off for run_id=%s",
        flow.state.run_id,
    )

    return run_ux_design_flow(flow)


__all__ = [
    "kick_off_ux_design_flow",
    "run_ux_design_draft",
    "run_ux_design_flow",
    "run_ux_design_review",
]
