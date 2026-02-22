"""Gemini-powered Requirements Breakdown agent module.

This agent takes a refined product idea and decomposes it into
structured, data-architect-ready product requirements — each feature
with AI agent capabilities, entity definitions, state transitions,
and user-role augmentation details.
"""

from crewai_productfeature_planner.agents.requirements_breakdown.agent import (
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_MIN_ITERATIONS,
    create_requirements_breakdown_agent,
    breakdown_requirements,
)

__all__ = [
    "DEFAULT_MAX_ITERATIONS",
    "DEFAULT_MIN_ITERATIONS",
    "create_requirements_breakdown_agent",
    "breakdown_requirements",
]
