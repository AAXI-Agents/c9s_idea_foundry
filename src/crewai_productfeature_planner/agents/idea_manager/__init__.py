"""Idea Manager agent module — unified idea refinement and iteration advisory.

Consolidates the former Idea Refiner (iterative refinement through
expert-user self-critique cycles) and Idea Agent (real-time in-thread
Q&A and steering) into a single agent with two operational tiers:

- ``tier="research"`` — deep iterative refinement (3-10 cycles)
- ``tier="basic"`` — fast conversational Q&A (~200-800 ms)
"""

from crewai_productfeature_planner.agents.idea_manager.agent import (
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_MIN_ITERATIONS,
    OptionsCallback,
    compute_average_confidence,
    create_idea_agent,
    create_idea_manager,
    create_idea_refiner,
    detect_direction_change,
    extract_steering_feedback,
    handle_idea_query,
    parse_evaluation_scores,
    refine_idea,
)

__all__ = [
    "DEFAULT_MAX_ITERATIONS",
    "DEFAULT_MIN_ITERATIONS",
    "OptionsCallback",
    "compute_average_confidence",
    "create_idea_agent",
    "create_idea_manager",
    "create_idea_refiner",
    "detect_direction_change",
    "extract_steering_feedback",
    "handle_idea_query",
    "parse_evaluation_scores",
    "refine_idea",
]
