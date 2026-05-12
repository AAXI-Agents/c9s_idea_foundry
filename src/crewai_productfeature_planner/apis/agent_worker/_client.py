"""Reusable HTTP client for calling Agent Worker endpoints.

Uses SSO ``client_credentials`` grant for service-to-service auth,
or forwards the user's Bearer token when ``user_token`` is provided.
Token is cached and auto-refreshed on 401.  Callers use the ``request``
method directly — each proxy route passes the method, path, and body.
"""

from __future__ import annotations

from typing import Any

import httpx

from crewai_productfeature_planner.apis.agent_worker._config import (
    AGENT_WORKER_BASE_URL,
    AGENT_WORKER_ENABLED,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# Cached service token (short-lived — refreshed on 401).
_cached_token: str | None = None


async def _get_service_token() -> str:
    """Obtain SSO service token via client_credentials grant."""
    global _cached_token  # noqa: PLW0603
    if _cached_token:
        return _cached_token

    import os

    sso_base = os.environ.get("SSO_BASE_URL", "")
    client_id = os.environ.get("SSO_CLIENT_ID", "")
    client_secret = os.environ.get("SSO_CLIENT_SECRET", "")

    if not all([sso_base, client_id, client_secret]):
        logger.warning("[AgentWorker] SSO credentials not configured for service token")
        return ""

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{sso_base}/oauth/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "scope": "pipeline:read pipeline:write",
                    "audience": "c9s_agent_worker",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                _cached_token = data.get("access_token", "")
                return _cached_token or ""
            logger.warning(
                "[AgentWorker] Service token request failed: %d", resp.status_code,
            )
    except httpx.RequestError as exc:
        logger.error("[AgentWorker] Service token request error: %s", exc)

    return ""


def _invalidate_token() -> None:
    """Clear cached token (e.g. on 401 response)."""
    global _cached_token  # noqa: PLW0603
    _cached_token = None


class AgentWorkerError(Exception):
    """Raised when Agent Worker returns an error or is unreachable."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Agent Worker {status_code}: {detail}")


async def _single_request(
    method: str,
    url: str,
    json_body: dict[str, Any] | None,
    token: str,
    timeout: float,
) -> dict[str, Any]:
    """Execute a single HTTP request to Agent Worker."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(
                method, url, json=json_body,
                headers={"Authorization": f"Bearer {token}"},
            )

        if resp.status_code >= 400:
            detail = resp.text[:500]
            logger.warning(
                "[AgentWorker] %s %s → %d: %s",
                method, url, resp.status_code, detail,
            )
            raise AgentWorkerError(resp.status_code, detail)

        if resp.status_code == 204:
            return {}

        return resp.json()

    except httpx.RequestError as exc:
        logger.error("[AgentWorker] %s %s network error: %s", method, url, exc)
        raise AgentWorkerError(503, f"Agent Worker unreachable: {exc}") from exc


async def request(
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    timeout: float = 15.0,
    user_token: str | None = None,
) -> dict[str, Any]:
    """Send a request to Agent Worker and return the JSON response.

    Raises ``AgentWorkerError`` on non-2xx responses.
    Raises ``httpx.RequestError`` on network failures.
    Auto-retries once on 401 when using service token.

    When ``user_token`` is provided, it is forwarded directly to Agent
    Worker (user token pass-through).  No retry on 401 in this mode.
    """
    if not AGENT_WORKER_ENABLED or not AGENT_WORKER_BASE_URL:
        raise AgentWorkerError(
            503, "Agent Worker integration is not enabled or configured",
        )

    url = f"{AGENT_WORKER_BASE_URL}{path}"

    # User token pass-through mode — single attempt, no refresh.
    if user_token:
        return await _single_request(method, url, json_body, user_token, timeout)

    # Service token mode — retry on 401.
    token = await _get_service_token()

    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.request(
                    method,
                    url,
                    json=json_body,
                    headers={"Authorization": f"Bearer {token}"},
                )

            if resp.status_code == 401 and attempt == 0:
                _invalidate_token()
                token = await _get_service_token()
                continue

            if resp.status_code >= 400:
                detail = resp.text[:500]
                logger.warning(
                    "[AgentWorker] %s %s → %d: %s",
                    method, path, resp.status_code, detail,
                )
                raise AgentWorkerError(resp.status_code, detail)

            # 204 No Content — return empty dict.
            if resp.status_code == 204:
                return {}

            return resp.json()

        except httpx.RequestError as exc:
            logger.error(
                "[AgentWorker] %s %s network error: %s",
                method, path, exc,
            )
            raise AgentWorkerError(
                503, f"Agent Worker unreachable: {exc}",
            ) from exc

    # Should not reach here, but just in case:
    raise AgentWorkerError(401, "Authentication failed after retry")
