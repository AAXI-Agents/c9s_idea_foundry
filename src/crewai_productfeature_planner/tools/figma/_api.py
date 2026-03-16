"""Figma REST API client for project and file operations.

Uses the Figma personal access token (``X-Figma-Token`` header) or
an OAuth2 bearer token for authenticated requests against the public
Figma REST API at ``https://api.figma.com``.

Supported operations:

* :func:`get_team_projects` — list projects in a team
* :func:`get_project_files` — list files in a project
* :func:`get_file_info` — get metadata for a single file
* :func:`refresh_oauth_token` — refresh an expired OAuth2 token
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

FIGMA_API_BASE = "https://api.figma.com"

# OAuth2 endpoints
FIGMA_OAUTH_TOKEN_URL = f"{FIGMA_API_BASE}/v1/oauth/token"
FIGMA_OAUTH_REFRESH_URL = f"{FIGMA_API_BASE}/v1/oauth/refresh"


class FigmaAPIError(Exception):
    """Raised when a Figma REST API call fails."""

    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


# ── internal helpers ─────────────────────────────────────────


def _build_headers(
    *,
    api_key: str = "",
    oauth_token: str = "",
) -> dict[str, str]:
    """Build auth headers — API key OR OAuth bearer token."""
    headers: dict[str, str] = {"Accept": "application/json"}
    if oauth_token:
        headers["Authorization"] = f"Bearer {oauth_token}"
    elif api_key:
        headers["X-Figma-Token"] = api_key
    return headers


def _request(
    method: str,
    path: str,
    *,
    api_key: str = "",
    oauth_token: str = "",
    body: dict | None = None,
    content_type: str = "application/json",
) -> dict[str, Any]:
    """Make an authenticated request to the Figma REST API."""
    url = f"{FIGMA_API_BASE}{path}"
    headers = _build_headers(api_key=api_key, oauth_token=oauth_token)

    data: bytes | None = None
    if body is not None:
        if content_type == "application/x-www-form-urlencoded":
            data = urllib.parse.urlencode(body).encode()
        else:
            data = json.dumps(body).encode()
        headers["Content-Type"] = content_type

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        msg = exc.read().decode() if exc.fp else str(exc)
        logger.error("[Figma API] %s %s → %d: %s", method, path, exc.code, msg)
        raise FigmaAPIError(
            f"Figma API {method} {path} failed ({exc.code}): {msg}",
            status=exc.code,
        ) from exc
    except urllib.error.URLError as exc:
        logger.error("[Figma API] %s %s → network error: %s", method, path, exc)
        raise FigmaAPIError(f"Network error: {exc}") from exc


# ── public API ───────────────────────────────────────────────


def get_team_projects(
    team_id: str,
    *,
    api_key: str = "",
    oauth_token: str = "",
) -> list[dict[str, Any]]:
    """Return the list of projects in a Figma team.

    Each project dict has ``id`` (int) and ``name`` (str).
    """
    resp = _request(
        "GET",
        f"/v1/teams/{team_id}/projects",
        api_key=api_key,
        oauth_token=oauth_token,
    )
    projects = resp.get("projects", [])
    logger.info(
        "[Figma API] Team %s has %d project(s)", team_id, len(projects),
    )
    return projects


def get_project_files(
    project_id: str,
    *,
    api_key: str = "",
    oauth_token: str = "",
) -> list[dict[str, Any]]:
    """Return the list of files in a Figma project.

    Each file dict has ``key`` (str), ``name`` (str),
    ``thumbnail_url`` (str), ``last_modified`` (str).
    """
    resp = _request(
        "GET",
        f"/v1/projects/{project_id}/files",
        api_key=api_key,
        oauth_token=oauth_token,
    )
    files = resp.get("files", [])
    logger.info(
        "[Figma API] Project %s has %d file(s)", project_id, len(files),
    )
    return files


def get_file_info(
    file_key: str,
    *,
    api_key: str = "",
    oauth_token: str = "",
) -> dict[str, Any]:
    """Return metadata for a single Figma file."""
    resp = _request(
        "GET",
        f"/v1/files/{file_key}?depth=1",
        api_key=api_key,
        oauth_token=oauth_token,
    )
    logger.info(
        "[Figma API] File %s: name=%s",
        file_key,
        resp.get("name", "?"),
    )
    return resp


def refresh_oauth_token(
    refresh_token: str,
    *,
    client_id: str = "",
    client_secret: str = "",
) -> dict[str, Any]:
    """Exchange a refresh token for a new OAuth2 access token.

    Uses HTTP Basic Auth with client_id:client_secret.

    Returns:
        Dict with ``access_token``, ``expires_in``, ``token_type``.
    """
    cid = client_id or os.environ.get("FIGMA_CLIENT_ID", "")
    csecret = client_secret or os.environ.get("FIGMA_CLIENT_SECRET", "")
    if not cid or not csecret:
        raise FigmaAPIError(
            "FIGMA_CLIENT_ID and FIGMA_CLIENT_SECRET required for token refresh"
        )

    credentials = base64.b64encode(f"{cid}:{csecret}".encode()).decode()
    url = FIGMA_OAUTH_REFRESH_URL
    body = urllib.parse.urlencode({"refresh_token": refresh_token}).encode()

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {credentials}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            result = json.loads(resp.read().decode())
            logger.info("[Figma API] OAuth token refreshed successfully")
            return result
    except urllib.error.HTTPError as exc:
        msg = exc.read().decode() if exc.fp else str(exc)
        raise FigmaAPIError(
            f"Token refresh failed ({exc.code}): {msg}",
            status=exc.code,
        ) from exc


def exchange_oauth_code(
    code: str,
    redirect_uri: str,
    *,
    client_id: str = "",
    client_secret: str = "",
) -> dict[str, Any]:
    """Exchange an OAuth2 authorization code for access + refresh tokens.

    Returns:
        Dict with ``access_token``, ``refresh_token``, ``expires_in``,
        ``token_type``, ``user_id_string``.
    """
    cid = client_id or os.environ.get("FIGMA_CLIENT_ID", "")
    csecret = client_secret or os.environ.get("FIGMA_CLIENT_SECRET", "")
    if not cid or not csecret:
        raise FigmaAPIError(
            "FIGMA_CLIENT_ID and FIGMA_CLIENT_SECRET required for code exchange"
        )

    credentials = base64.b64encode(f"{cid}:{csecret}".encode()).decode()
    url = FIGMA_OAUTH_TOKEN_URL
    body = urllib.parse.urlencode({
        "redirect_uri": redirect_uri,
        "code": code,
        "grant_type": "authorization_code",
    }).encode()

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {credentials}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            result = json.loads(resp.read().decode())
            logger.info(
                "[Figma API] OAuth code exchanged, user=%s",
                result.get("user_id_string", "?"),
            )
            return result
    except urllib.error.HTTPError as exc:
        msg = exc.read().decode() if exc.fp else str(exc)
        raise FigmaAPIError(
            f"Code exchange failed ({exc.code}): {msg}",
            status=exc.code,
        ) from exc
