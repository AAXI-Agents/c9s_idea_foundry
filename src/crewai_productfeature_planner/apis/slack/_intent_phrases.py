"""Keyword-phrase constants and phrase-based intent fallback.

These phrase tuples provide a safety-net matching layer when the LLM
interpretation is unavailable or uncertain.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Phrase constants for text-level safety-net matching
# ---------------------------------------------------------------------------

_IDEA_PHRASES = (
    "iterate an idea", "iterate a new idea", "iterate idea",
    "new idea", "start an idea", "brainstorm an idea",
    "refine my idea", "refine an idea", "plan an idea",
    "work on an idea", "create a prd", "create prd",
    "plan a feature", "build a prd", "help me iterate",
    "let's iterate", "let's brainstorm",
    "create idea", "create an idea", "create new idea",
    "create a new idea",
)
_CREATE_PROJECT_PHRASES = (
    "create a project", "create project", "new project",
    "set up a project", "setup a project", "start a project",
    "create a new project", "create new project",
    "setup project", "set up project",
    "start a new project", "start new project",
    "add a project", "add project", "add new project",
    "i need a project", "need a project",
    "project for this channel", "project for channel",
)
_LIST_PROJECTS_PHRASES = (
    "list projects", "show projects", "available projects",
    "show me available projects", "what projects",
    "which projects", "my projects", "all projects",
    "show me projects", "view projects",
)
_LIST_IDEAS_PHRASES = (
    "list ideas", "list of ideas", "show ideas",
    "my ideas", "show my ideas", "current ideas",
    "ideas in progress", "what ideas",
    "which ideas", "view ideas",
)
_LIST_PRODUCTS_PHRASES = (
    "list products", "show products", "list completed",
    "show completed ideas", "completed ideas",
    "completed products", "show completed",
    "my products", "show my products",
    "delivery status", "ready for delivery",
    "products ready", "what products",
    "which products", "view products",
)
_SWITCH_PROJECT_PHRASES = (
    "switch project", "change project", "different project",
    "another project", "swap project", "switch to project",
    "change to project", "switch to another project",
    "change to another project", "use a different project",
)
_END_SESSION_PHRASES = (
    "end session", "stop session", "close session",
    "i'm done", "im done", "quit session",
)
_CURRENT_PROJECT_PHRASES = (
    "current project", "my project", "which project",
    "active project", "what project",
)
_CONFIGURE_MEMORY_PHRASES = (
    "configure memory", "configure more memory",
    "project memory", "setup memory",
    "set up memory", "memory settings", "memory config",
    "edit memory", "update memory", "view memory",
    "show memory", "add memory", "add more memory",
    "manage memory", "memory configuration",
    "configure knowledge", "configure more knowledge",
    "project knowledge", "setup knowledge",
    "set up knowledge", "knowledge settings", "knowledge config",
    "edit knowledge", "update knowledge", "view knowledge",
    "show knowledge", "add knowledge", "add more knowledge",
    "manage knowledge", "knowledge configuration",
)
_UPDATE_CONFIG_PHRASES = (
    "confluence key", "confluence space key", "jira key",
    "jira project key", "set confluence", "add confluence",
    "add jira", "configure confluence", "configure jira",
    "space key", "parent page id", "parent id",
    "update config", "set config",
)
_RESUME_PRD_PHRASES = (
    "resume prd", "resume prd flow", "resume flow",
    "continue prd", "continue prd flow", "continue flow",
    "resume the prd", "continue the prd", "resume the flow",
    "pick up where", "resume run", "resume generation",
    "unpause", "unpause prd", "unpause flow",
    "resume idea", "continue idea",
)
_RESTART_PRD_PHRASES = (
    "restart prd", "restart prd flow", "restart flow",
    "restart scan", "restart from scratch", "restart from beginning",
    "start over", "start the prd over", "redo the prd",
    "redo prd", "restart the prd", "restart the flow",
    "restart the iteration", "restart iteration",
    "reiterate from start", "reiterate idea", "reiterate from beginning",
    "rescan", "rescan idea",
)
_CREATE_JIRA_PHRASES = (
    "create jira", "create jira tickets", "jira tickets",
    "make jira tickets", "make jira", "generate jira",
    "jira skeleton", "set up jira", "setup jira",
    "jira epics", "generate jira tickets",
)


# ---------------------------------------------------------------------------
# Phrase-based fallback when LLM interpretation fails
# ---------------------------------------------------------------------------

_PHRASE_INTENT_MAP: list[tuple[tuple[str, ...], str]] = [
    (_RESTART_PRD_PHRASES, "restart_prd"),
    (_RESUME_PRD_PHRASES, "resume_prd"),
    (_CREATE_JIRA_PHRASES, "create_jira"),
    (_IDEA_PHRASES, "create_prd"),
    (_CONFIGURE_MEMORY_PHRASES, "configure_memory"),
    (_UPDATE_CONFIG_PHRASES, "update_config"),
    (_LIST_IDEAS_PHRASES, "list_ideas"),
    (_LIST_PRODUCTS_PHRASES, "list_products_intent"),
    (_LIST_PROJECTS_PHRASES, "list_projects"),
    (_SWITCH_PROJECT_PHRASES, "switch_project"),
    (_END_SESSION_PHRASES, "end_session"),
    (_CURRENT_PROJECT_PHRASES, "current_project"),
    (_CREATE_PROJECT_PHRASES, "create_project"),
]


def _phrase_fallback(text: str) -> dict:
    """Derive intent from keyword phrases when the LLM is unavailable."""
    lower = text.lower().strip("* \t\n")
    for phrases, intent in _PHRASE_INTENT_MAP:
        if any(p in lower for p in phrases):
            logger.info("Phrase-fallback matched intent=%s for %r", intent, text[:80])
            return {"intent": intent, "idea": None, "reply": ""}
    # Check for common greetings/help
    if lower in ("help", "help me", "what can you do"):
        return {"intent": "help", "idea": None, "reply": ""}
    if lower in ("hi", "hello", "hey", "yo", "sup"):
        return {"intent": "greeting", "idea": None, "reply": ""}
    return {"intent": "unknown", "idea": None, "reply": ""}
