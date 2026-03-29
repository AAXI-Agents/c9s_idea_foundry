"""Flows package — orchestrates multi-step agent workflows.

Sub-modules:
    - ``prd_flow``             — PRDFlow class (slim orchestrator)
    - ``ux_design_flow``       — Standalone UX design flow (post-PRD)
    - ``_constants``           — constants, utilities, exceptions, PRDState
    - ``_agents``              — agent creation, parallel execution
    - ``_executive_summary``   — Phase 1 executive summary iteration
    - ``_section_loop``        — Phase 2 section critique→refine loop
    - ``_finalization``        — save, finalize, post-completion delivery
    - ``_ux_design``           — 2-phase UX design (draft + review)
"""

from crewai_productfeature_planner.flows.prd_flow import (
    PRDFlow,
    cleanup_callbacks,
    register_callbacks,
)
from crewai_productfeature_planner.flows.ux_design_flow import (
    kick_off_ux_design_flow,
)

__all__ = [
    "PRDFlow",
    "cleanup_callbacks",
    "kick_off_ux_design_flow",
    "register_callbacks",
]
