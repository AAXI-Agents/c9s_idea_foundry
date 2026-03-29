"""Idea Agent module — in-thread analyst for active idea iterations.

Routes user questions about in-progress ideas to a context-aware agent
that can answer with specific iteration data and produce steering
recommendations for downstream agents.
"""

from crewai_productfeature_planner.agents.idea_agent.agent import (
    create_idea_agent,
    extract_steering_feedback,
    handle_idea_query,
)

__all__ = [
    "create_idea_agent",
    "extract_steering_feedback",
    "handle_idea_query",
]
