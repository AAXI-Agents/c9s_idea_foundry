"""Low-level HTTP transport for the Jira REST API."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request

import certifi

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)


def _jira_request(
    method: str,
    url: str,
    *,
    auth_header: str,
    data: dict | None = None,
    timeout: int = 30,
) -> dict:
    """Execute an HTTP request against the Jira REST API.

    Args:
        method: HTTP method (GET, POST, PUT).
        url: Full URL.
        auth_header: Basic-auth header value.
        data: JSON body (for POST/PUT).
        timeout: Request timeout in seconds.

    Returns:
        Parsed JSON response.

    Raises:
        RuntimeError: On non-2xx responses.
    """
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Authorization": auth_header,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    ssl_ctx = ssl.create_default_context(cafile=certifi.where())

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl_ctx) as resp:
            raw = resp.read().decode()
            if not raw.strip():
                return {}
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode() if exc.fp else ""
        logger.error(
            "[Jira] %s %s → %d: %s",
            method, url, exc.code, error_body[:500],
        )
        raise RuntimeError(
            f"Jira API error {exc.code}: {error_body[:300]}"
        ) from exc
