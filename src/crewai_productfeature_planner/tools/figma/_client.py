"""Low-level HTTP client for the Figma REST API.

Handles authentication, request building, and JSON parsing.
Uses ``urllib`` (stdlib) to avoid adding external HTTP dependencies.
"""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.request

import certifi

from crewai_productfeature_planner.scripts.logging_config import get_logger
from crewai_productfeature_planner.tools.figma._config import (
    DEFAULT_POLL_INTERVAL,
    DEFAULT_POLL_TIMEOUT,
    FIGMA_API_BASE,
    get_figma_access_token,
    get_figma_team_id,
)

logger = get_logger(__name__)

# Reusable SSL context for HTTPS requests.
_SSL_CTX = ssl.create_default_context(cafile=certifi.where())


class FigmaMakeError(Exception):
    """Raised when a Figma Make API call fails."""


def _request(
    method: str,
    path: str,
    *,
    body: dict | None = None,
    timeout: int = 60,
) -> dict:
    """Send an authenticated request to the Figma API.

    Returns the parsed JSON response body.
    """
    token = get_figma_access_token()
    if not token:
        raise FigmaMakeError("FIGMA_ACCESS_TOKEN is not set")

    url = f"{FIGMA_API_BASE}{path}"
    headers = {
        "X-Figma-Token": token,
        "Content-Type": "application/json",
    }

    data = json.dumps(body).encode("utf-8") if body else None

    req = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = ""
        try:
            error_body = exc.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass
        logger.error(
            "[Figma] %s %s → HTTP %d: %s",
            method, path, exc.code, error_body[:500],
        )
        raise FigmaMakeError(
            f"Figma API returned HTTP {exc.code}: {error_body[:200]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise FigmaMakeError(f"Figma API connection error: {exc}") from exc


def submit_figma_make(prompt: str) -> dict:
    """Submit a design generation request to Figma Make.

    Calls ``POST /v1/ai/make`` with the design prompt and team context.
    Returns the API response containing ``request_id`` and ``status``.
    """
    team_id = get_figma_team_id()
    payload: dict = {"prompt": prompt}
    if team_id:
        payload["team_id"] = team_id

    logger.info(
        "[Figma] Submitting Make request (prompt=%d chars, team=%s)",
        len(prompt), team_id or "(default)",
    )
    return _request("POST", "/v1/ai/make", body=payload)


def poll_figma_make(
    request_id: str,
    *,
    poll_interval: int = DEFAULT_POLL_INTERVAL,
    poll_timeout: int = DEFAULT_POLL_TIMEOUT,
) -> dict:
    """Poll Figma Make until the design is complete or timed out.

    Returns the final API response containing ``file_key`` and
    ``file_url`` when the design is ready.

    Raises :class:`FigmaMakeError` on timeout or API failure.
    """
    deadline = time.monotonic() + poll_timeout
    path = f"/v1/ai/make/{request_id}"

    while time.monotonic() < deadline:
        resp = _request("GET", path)
        status = resp.get("status", "")

        if status == "completed":
            logger.info(
                "[Figma] Make request %s completed → file_key=%s",
                request_id, resp.get("file_key", "?"),
            )
            return resp

        if status in ("failed", "error"):
            error_msg = resp.get("error", "Unknown error")
            raise FigmaMakeError(
                f"Figma Make request {request_id} failed: {error_msg}"
            )

        logger.debug(
            "[Figma] Make request %s status=%s — polling in %ds",
            request_id, status, poll_interval,
        )
        time.sleep(poll_interval)

    raise FigmaMakeError(
        f"Figma Make request {request_id} timed out after {poll_timeout}s"
    )
