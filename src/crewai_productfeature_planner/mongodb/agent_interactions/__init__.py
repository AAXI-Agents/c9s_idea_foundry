"""agent_interactions sub-package — persistence for agent interaction tracking.

Re-exports the public repository API so callers can do::

    from crewai_productfeature_planner.mongodb.agent_interactions import log_interaction, ...
"""

from crewai_productfeature_planner.mongodb.agent_interactions.repository import (
    AGENT_INTERACTIONS_COLLECTION,
    find_interactions,
    find_interactions_by_intent,
    find_interactions_by_source,
    get_interaction,
    list_interactions,
    log_interaction,
)

__all__ = [
    "AGENT_INTERACTIONS_COLLECTION",
    "find_interactions",
    "find_interactions_by_intent",
    "find_interactions_by_source",
    "get_interaction",
    "list_interactions",
    "log_interaction",
]
