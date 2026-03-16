"""Figma Make configuration and environment helpers.

Environment variables (fallbacks when project config is absent):

* ``FIGMA_SESSION_DIR``   — Directory for Playwright session state
                            (default ``~/.figma_session``)
* ``FIGMA_MAKE_TIMEOUT``  — Max seconds to wait for design generation
                            (default ``300``)
* ``FIGMA_HEADLESS``      — Run browser headless (``true`` | ``false``,
                            default ``true``)
* ``FIGMA_CLIENT_ID``     — OAuth2 app client ID (for token exchange)
* ``FIGMA_CLIENT_SECRET`` — OAuth2 app client secret

Project-level fields (stored in ``projectConfig`` collection):

* ``figma_api_key``             — Figma personal access token
* ``figma_team_id``             — Figma team ID
* ``figma_oauth_token``         — OAuth2 access token
* ``figma_oauth_refresh_token`` — OAuth2 refresh token
* ``figma_oauth_expires_at``    — ISO-8601 token expiry
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# Figma Make entry-point URL.
FIGMA_MAKE_URL = "https://www.figma.com/make/new"

# OAuth2 authorization URL template.
FIGMA_OAUTH_URL = "https://www.figma.com/oauth"

# Maximum time (seconds) to wait for Figma Make to finish generating.
DEFAULT_MAKE_TIMEOUT = 300

# Default directory for persisted Playwright browser state.
DEFAULT_SESSION_DIR = os.path.expanduser("~/.figma_session")

# OAuth2 local redirect (for the Playwright-automated OAuth flow).
OAUTH_REDIRECT_URI = "http://localhost:3000/figma/callback"


def get_figma_session_dir() -> str:
    """Return the directory for Playwright session state."""
    return os.environ.get("FIGMA_SESSION_DIR", DEFAULT_SESSION_DIR).strip()


def get_figma_session_path() -> str:
    """Return the full path to the Playwright state JSON file."""
    return os.path.join(get_figma_session_dir(), "state.json")


def get_figma_make_timeout() -> int:
    """Return the Figma Make timeout in seconds."""
    raw = os.environ.get("FIGMA_MAKE_TIMEOUT", "")
    try:
        return int(raw)
    except (ValueError, TypeError):
        return DEFAULT_MAKE_TIMEOUT


def get_figma_headless() -> bool:
    """Return ``True`` if the browser should run headless."""
    return os.environ.get("FIGMA_HEADLESS", "true").strip().lower() != "false"


def get_figma_client_id() -> str:
    """Return the Figma OAuth2 client ID."""
    return os.environ.get("FIGMA_CLIENT_ID", "").strip()


def get_figma_client_secret() -> str:
    """Return the Figma OAuth2 client secret."""
    return os.environ.get("FIGMA_CLIENT_SECRET", "").strip()


# ── Project-level credential resolution ──────────────────────


def get_figma_credentials(
    project_config: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Resolve Figma credentials from project config.

    Returns a dict with ``api_key``, ``oauth_token``, ``team_id``,
    ``oauth_refresh_token``, ``oauth_expires_at``.  All values are
    strings (possibly empty).
    """
    cfg = project_config or {}
    return {
        "api_key": cfg.get("figma_api_key", ""),
        "oauth_token": cfg.get("figma_oauth_token", ""),
        "oauth_refresh_token": cfg.get("figma_oauth_refresh_token", ""),
        "oauth_expires_at": cfg.get("figma_oauth_expires_at", ""),
        "team_id": cfg.get("figma_team_id", ""),
    }


def has_figma_credentials(
    project_config: dict[str, Any] | None = None,
) -> bool:
    """Return ``True`` if any Figma auth method is available.

    Checks (in order):
    1. Project-level API key
    2. Project-level OAuth token (not expired)
    3. Playwright session state file on disk
    """
    creds = get_figma_credentials(project_config)
    if creds["api_key"]:
        return True
    if creds["oauth_token"] and not _oauth_expired(creds["oauth_expires_at"]):
        return True
    return os.path.isfile(get_figma_session_path())


def _oauth_expired(expires_at: str) -> bool:
    """Return ``True`` if the OAuth token expiry has passed."""
    if not expires_at:
        return True
    try:
        expiry = datetime.fromisoformat(expires_at)
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) >= expiry
    except (ValueError, TypeError):
        return True
