"""``ideas`` collection — Idea domain model with feature tracking.

This module provides CRUD operations for the ``ideas`` collection,
which holds Idea entities that link to ``workingIdeas`` (PRD flow runs)
and ``ideationSessions`` (multi-step Q&A sessions).

Re-exports all public repository symbols.
"""

from crewai_productfeature_planner.mongodb.ideas.repository import (
    IDEAS_COLLECTION,
    count_ideas,
    create_idea,
    delete_idea,
    find_idea_by_session,
    get_idea,
    list_ideas,
    save_design_url,
    set_active_run,
    update_features,
    update_idea,
    update_idea_status,
    update_overall_completion,
)

__all__ = [
    "IDEAS_COLLECTION",
    "count_ideas",
    "create_idea",
    "delete_idea",
    "find_idea_by_session",
    "get_idea",
    "list_ideas",
    "save_design_url",
    "set_active_run",
    "update_features",
    "update_idea",
    "update_idea_status",
    "update_overall_completion",
]
