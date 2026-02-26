"""Shared helpers for orchestrator stage modules.

Credential checks, status printing, and other utilities used across
multiple stage factories.  Kept here to avoid circular imports and
to provide a single, small file for AI agents to load.
"""

from __future__ import annotations

import os

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)


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
