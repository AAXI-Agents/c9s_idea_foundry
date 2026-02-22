"""Gemini-powered Idea Refinement agent module.

This agent acts as an industry-expert user to iteratively refine a raw
product idea before PRD generation begins.
"""

from crewai_productfeature_planner.agents.idea_refiner.agent import (
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_MIN_ITERATIONS,
    create_idea_refiner,
    refine_idea,
)

__all__ = [
    "DEFAULT_MAX_ITERATIONS",
    "DEFAULT_MIN_ITERATIONS",
    "create_idea_refiner",
    "refine_idea",
]
