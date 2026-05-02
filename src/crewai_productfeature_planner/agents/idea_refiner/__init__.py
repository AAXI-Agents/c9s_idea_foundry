"""Idea Refiner module — DEPRECATED, use idea_manager instead.

This module re-exports from the consolidated Idea Manager agent for
backward compatibility.  All new code should import from
``crewai_productfeature_planner.agents.idea_manager``.
"""

from crewai_productfeature_planner.agents.idea_manager import (
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_MIN_ITERATIONS,
    OptionsCallback,
    compute_average_confidence,
    create_idea_refiner,
    detect_direction_change,
    parse_evaluation_scores,
    refine_idea,
)

__all__ = [
    "DEFAULT_MAX_ITERATIONS",
    "DEFAULT_MIN_ITERATIONS",
    "OptionsCallback",
    "compute_average_confidence",
    "create_idea_refiner",
    "detect_direction_change",
    "parse_evaluation_scores",
    "refine_idea",
]
