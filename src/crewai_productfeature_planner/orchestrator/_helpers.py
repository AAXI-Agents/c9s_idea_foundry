"""Shared helpers for orchestrator stage modules.

Credential checks, status printing, and other utilities used across
multiple stage factories.  Kept here to avoid circular imports and
to provide a single, small file for AI agents to load.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from crewai_productfeature_planner.scripts.logging_config import get_logger

if TYPE_CHECKING:
    from crewai_productfeature_planner.apis.prd.models import PRDDraft

logger = get_logger(__name__)


# ── Page title construction ───────────────────────────────────────────

_MAX_TITLE_LEN = 80


def make_page_title(idea: str | None, *, fallback: str = "Product Requirements") -> str:
    """Build a short Confluence / Jira page title from the raw idea text.

    Returns the idea text truncated to *_MAX_TITLE_LEN* characters.
    Falls back to *fallback* when *idea* is empty or ``None``.
    """
    text = (idea or "").strip()
    if not text:
        return fallback
    if len(text) > _MAX_TITLE_LEN:
        text = text[:_MAX_TITLE_LEN].rstrip() + "…"
    return text


# ── Credential checks ────────────────────────────────────────────────


def _has_gemini_credentials() -> bool:
    """Return True when at least one Gemini auth mechanism is configured."""
    return bool(
        os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
    )


def _has_confluence_credentials() -> bool:
    """Return True when all required Confluence env vars are set."""
    from crewai_productfeature_planner.tools.confluence_tool import (
        _has_confluence_credentials as _check,
    )
    return _check()


def _has_jira_credentials() -> bool:
    """Return True when all required Jira env vars are set."""
    from crewai_productfeature_planner.tools.jira_tool import (
        _has_jira_credentials as _check,
    )
    return _check()


# ── CLI output ────────────────────────────────────────────────────────


def _print_delivery_status(message: str) -> None:
    """Print a delivery status line to the CLI with an orchestrator prefix."""
    print(f"  \033[36m[Orchestrator]\033[0m {message}")


# ── PRD context extraction ────────────────────────────────────────────

# Additional PRD sections that enrich Jira ticket context beyond the
# functional requirements.  Each tuple is (section_key, display_title).
_EXTRA_PRD_SECTIONS: list[tuple[str, str]] = [
    ("no_functional_requirements", "Non-Functional Requirements"),
    ("edge_cases", "Edge Cases"),
    ("error_handling", "Error Handling"),
    ("user_personas", "User Personas"),
    ("dependencies", "Dependencies"),
]


def build_additional_prd_context_from_draft(draft: "PRDDraft") -> str:
    """Extract additional PRD sections from a :class:`PRDDraft` object.

    Returns a formatted string block with all available extra sections
    (non-functional requirements, edge cases, error handling, user
    personas, dependencies).  Returns empty string when none are found.
    """
    blocks: list[str] = []
    for section_key, title in _EXTRA_PRD_SECTIONS:
        section = draft.get_section(section_key)
        if section and section.content and section.content.strip():
            blocks.append(f"### {title}\n{section.content.strip()}")
    if not blocks:
        return ""
    return "## Additional PRD Context\n\n" + "\n\n".join(blocks)


def build_additional_prd_context_from_doc(doc: dict) -> str:
    """Extract additional PRD sections from a raw MongoDB document.

    Used by :func:`_startup_delivery.build_startup_delivery_crew` when
    the PRDDraft model is not available.  Falls back to reading the
    ``section`` dict from the document.

    Returns a formatted string block, or empty string when no extra
    sections are found.
    """
    section_obj = doc.get("section", {})
    if not isinstance(section_obj, dict):
        return ""

    blocks: list[str] = []
    for section_key, title in _EXTRA_PRD_SECTIONS:
        iters = section_obj.get(section_key, [])
        if isinstance(iters, list) and iters:
            latest = iters[-1]
            if isinstance(latest, dict):
                content = latest.get("content", "")
                if content and content.strip():
                    blocks.append(f"### {title}\n{content.strip()}")
    if not blocks:
        return ""
    return "## Additional PRD Context\n\n" + "\n\n".join(blocks)
