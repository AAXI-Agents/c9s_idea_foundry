"""Figma API configuration and environment helpers."""

import os

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# Figma REST API base URL.
FIGMA_API_BASE = "https://api.figma.com"

# Default poll interval (seconds) while waiting for Figma Make to finish.
DEFAULT_POLL_INTERVAL = 10

# Maximum time (seconds) to wait for Figma Make completion before timing out.
DEFAULT_POLL_TIMEOUT = 300


def get_figma_access_token() -> str:
    """Return the Figma access token from the environment, or ``""``."""
    return os.environ.get("FIGMA_ACCESS_TOKEN", "").strip()


def get_figma_team_id() -> str:
    """Return the Figma team ID from the environment, or ``""``."""
    return os.environ.get("FIGMA_TEAM_ID", "").strip()


def has_figma_credentials() -> bool:
    """Return ``True`` if Figma access token is configured."""
    return bool(get_figma_access_token())
