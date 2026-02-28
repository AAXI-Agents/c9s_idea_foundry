"""Centralised version and changelog (codex) for the application.

Every deployment-worthy change gets an entry in ``_CODEX``.  The latest
entry's version is the canonical application version, surfaced in:

* Startup log lines
* ``GET /health`` and ``GET /version`` API responses
* The FastAPI ``app.version`` metadata / Swagger UI

Versioning scheme: **Major.Minor.Iteration**
    Major     – breaking / architectural changes
    Minor     – new feature or significant enhancement
    Iteration – bug-fix, tweak, or incremental improvement
"""

from __future__ import annotations

from datetime import date
from typing import NamedTuple


class CodexEntry(NamedTuple):
    """Single codex (changelog) record."""

    version: str
    date: date
    summary: str


# ---------------------------------------------------------------------------
# Codex – append new entries at the **bottom**
# ---------------------------------------------------------------------------

_CODEX: list[CodexEntry] = [
    CodexEntry(
        version="0.1.0",
        date=date(2026, 2, 14),
        summary="Initial release — PRD generation flow, MongoDB persistence, FastAPI server.",
    ),
    CodexEntry(
        version="0.1.1",
        date=date(2026, 2, 25),
        summary=(
            "Slack OAuth refactoring — per-team tokens stored in MongoDB "
            "slackOAuth collection; removed .env token dependency."
        ),
    ),
    CodexEntry(
        version="0.1.2",
        date=date(2026, 2, 28),
        summary=(
            "Intent classification fix — added create_project intent to "
            "Gemini/OpenAI prompts with few-shot examples and text-level "
            "fallback detection so 'create a project' no longer loops to "
            "the project-selection prompt."
        ),
    ),
    CodexEntry(
        version="0.1.3",
        date=date(2026, 2, 28),
        summary=(
            "Version control & codex — centralised version module, "
            "GET /version endpoint, version in health response and "
            "startup logs for deployment traceability."
        ),
    ),
    CodexEntry(
        version="0.1.4",
        date=date(2026, 2, 28),
        summary=(
            "Thread reply awareness — app_mention events with pending "
            "state (e.g. awaiting project name) now route through the "
            "thread handler instead of re-interpreting via LLM. Other "
            "users' replies are ignored while waiting for the initiating "
            "user's input, ensuring session isolation."
        ),
    ),
    CodexEntry(
        version="0.1.5",
        date=date(2026, 2, 28),
        summary=(
            "Intent fix & project setup wizard — 'iterate an idea' no "
            "longer misclassified as create_project when a session is "
            "active.  Project creation now walks through a 3-step setup "
            "wizard (Confluence space key, Jira project key, Confluence "
            "parent page ID) matching the CLI experience."
        ),
    ),
    CodexEntry(
        version="0.1.6",
        date=date(2026, 2, 28),
        summary=(
            "Comprehensive intent audit — added 5 new LLM intents "
            "(list_projects, switch_project, end_session, current_project, "
            "configure_memory) to Gemini/OpenAI prompts.  Replaced brittle "
            "exact-match text commands with broader phrase-matching + LLM "
            "intent routing.  'show me available projects' and other natural "
            "phrasing now works correctly.  Updated help text to list all "
            "available capabilities."
        ),
    ),
]

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

#: Current application version (derived from the latest codex entry).
__version__: str = _CODEX[-1].version


def get_version() -> str:
    """Return the current application version string."""
    return __version__


def get_codex() -> list[dict]:
    """Return the full codex as a list of dicts (JSON-serialisable)."""
    return [
        {
            "version": entry.version,
            "date": entry.date.isoformat(),
            "summary": entry.summary,
        }
        for entry in _CODEX
    ]


def get_latest_codex_entry() -> dict:
    """Return only the most recent codex entry as a dict."""
    entry = _CODEX[-1]
    return {
        "version": entry.version,
        "date": entry.date.isoformat(),
        "summary": entry.summary,
    }
