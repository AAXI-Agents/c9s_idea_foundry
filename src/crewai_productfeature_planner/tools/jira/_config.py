"""Jira configuration, context variables, environment, and auth helpers."""

from __future__ import annotations

import contextvars
import base64
import os
from contextlib import contextmanager
from typing import Generator

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# ── Context-variable overrides (set by orchestrator with project config) ──

_project_key_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "jira_project_key_override", default="",
)


def set_jira_project_key(key: str) -> contextvars.Token[str]:
    """Set the Jira project key for the current context.

    Returns a reset token for use with :meth:`contextvars.ContextVar.reset`.
    """
    return _project_key_ctx.set(key)


@contextmanager
def jira_project_context(
    *,
    project_key: str = "",
) -> Generator[None, None, None]:
    """Context manager that sets a project-level Jira project key override.

    Usage::

        with jira_project_context(project_key="MYPROJ"):
            create_jira_issue(summary="...", run_id=rid)
    """
    token: contextvars.Token | None = None
    if project_key:
        token = _project_key_ctx.set(project_key)
    try:
        yield
    finally:
        if token is not None:
            _project_key_ctx.reset(token)


def _get_jira_env(*, project_key: str | None = None) -> dict[str, str]:
    """Read Jira config from environment with optional overrides.

    Resolution order for ``project_key``:

    1. Explicit *project_key* parameter
    2. ``_project_key_ctx`` context variable
    3. ``JIRA_PROJECT_KEY`` environment variable

    Returns:
        Dict with keys ``base_url``, ``project_key``, ``username``,
        ``api_token``.

    Raises:
        EnvironmentError: If required vars are missing.
    """
    base_url = os.environ.get("ATLASSIAN_BASE_URL", "").rstrip("/")
    resolved_project_key = (
        project_key
        or _project_key_ctx.get()
        or os.environ.get("JIRA_PROJECT_KEY", "")
    )
    username = os.environ.get("ATLASSIAN_USERNAME", "")
    api_token = os.environ.get("ATLASSIAN_API_TOKEN", "")

    missing: list[str] = []
    if not base_url:
        missing.append("ATLASSIAN_BASE_URL")
    if not resolved_project_key:
        missing.append("JIRA_PROJECT_KEY")
    if not username:
        missing.append("ATLASSIAN_USERNAME")
    if not api_token:
        missing.append("ATLASSIAN_API_TOKEN")

    if missing:
        raise EnvironmentError(
            f"Jira tool requires: {', '.join(missing)}"
        )

    return {
        "base_url": base_url,
        "project_key": resolved_project_key,
        "username": username,
        "api_token": api_token,
    }


def _has_jira_credentials() -> bool:
    """Return ``True`` when all required Jira env vars are set."""
    try:
        _get_jira_env()
        return True
    except EnvironmentError:
        return False


def _build_auth_header(username: str, api_token: str) -> str:
    """Build a Basic-auth header value."""
    credentials = f"{username}:{api_token}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"
