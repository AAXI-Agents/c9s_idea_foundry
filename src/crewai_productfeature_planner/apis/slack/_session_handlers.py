"""Session-related Slack handlers -- project, setup wizard, memory.

This module is a backward-compatible re-export facade.  All symbols are
defined in focused sub-modules and re-exported here so that existing
imports continue to work.
"""

# Reply helper and intro
from ._session_reply import INTRO_MESSAGE, post_intro, reply

# Project selection, switching, creation, and setup wizard
from ._session_project import (
    handle_create_project_intent,
    handle_current_project,
    handle_end_session,
    handle_project_name_reply,
    handle_project_setup_reply,
    handle_switch_project,
    prompt_project_selection,
)

# Memory configuration and project config updates
from ._session_memory import (
    handle_configure_memory,
    handle_memory_reply,
    handle_update_config,
)

# Idea listing
from ._session_ideas import _backfill_missing_idea_titles, handle_list_ideas

# Product listing (completed ideas for delivery)
from ._session_products import handle_list_products

__all__ = [
    "reply",
    "INTRO_MESSAGE",
    "post_intro",
    "prompt_project_selection",
    "handle_switch_project",
    "handle_end_session",
    "handle_current_project",
    "handle_create_project_intent",
    "handle_project_name_reply",
    "handle_project_setup_reply",
    "handle_configure_memory",
    "handle_memory_reply",
    "handle_update_config",
    "_backfill_missing_idea_titles",
    "handle_list_ideas",
    "handle_list_products",
]
