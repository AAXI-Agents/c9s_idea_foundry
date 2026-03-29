"""User suggestions collection — tracks ambiguous intents for self-learning."""

from crewai_productfeature_planner.mongodb.user_suggestions.repository import (
    USER_SUGGESTIONS_COLLECTION,
    find_suggestions_by_project,
    log_suggestion,
)

__all__ = [
    "USER_SUGGESTIONS_COLLECTION",
    "find_suggestions_by_project",
    "log_suggestion",
]
