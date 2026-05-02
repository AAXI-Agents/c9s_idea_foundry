"""Idea Agent module — DEPRECATED, use idea_manager instead.

This module re-exports from the consolidated Idea Manager agent for
backward compatibility.  All new code should import from
``crewai_productfeature_planner.agents.idea_manager``.
"""

from crewai_productfeature_planner.agents.idea_manager import (
    create_idea_agent,
    extract_steering_feedback,
    handle_idea_query,
)

__all__ = [
    "create_idea_agent",
    "extract_steering_feedback",
    "handle_idea_query",
]
