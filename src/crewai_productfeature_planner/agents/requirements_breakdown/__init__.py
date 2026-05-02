"""Requirements Breakdown module — DEPRECATED, use product_manager instead.

This module re-exports from the consolidated Product Manager agent for
backward compatibility.  All new code should import from
``crewai_productfeature_planner.agents.product_manager``.
"""

from crewai_productfeature_planner.agents.product_manager import (
    DEFAULT_REQUIREMENTS_MAX_ITERATIONS as DEFAULT_MAX_ITERATIONS,
    DEFAULT_REQUIREMENTS_MIN_ITERATIONS as DEFAULT_MIN_ITERATIONS,
    breakdown_requirements,
    create_requirements_breakdown_agent,
)

__all__ = [
    "DEFAULT_MAX_ITERATIONS",
    "DEFAULT_MIN_ITERATIONS",
    "create_requirements_breakdown_agent",
    "breakdown_requirements",
]
