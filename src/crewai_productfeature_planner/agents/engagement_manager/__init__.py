"""Engagement Manager agent module.

This agent handles unknown or ambiguous user intents by guiding users
to the correct system action or interaction menu, and orchestrates the
full idea-to-PRD lifecycle with heartbeat updates and user steering.
"""

from crewai_productfeature_planner.agents.engagement_manager.agent import (
    create_engagement_manager,
    detect_user_steering,
    generate_heartbeat,
    handle_unknown_intent,
    make_heartbeat_progress_callback,
    orchestrate_idea_to_prd,
)

__all__ = [
    "create_engagement_manager",
    "detect_user_steering",
    "generate_heartbeat",
    "handle_unknown_intent",
    "make_heartbeat_progress_callback",
    "orchestrate_idea_to_prd",
]
