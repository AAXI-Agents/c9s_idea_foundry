"""Generic Agent Worker proxy — ``/aw/{path:path}``.

Catch-all reverse proxy that forwards any request to Agent Worker.
Specific typed routes (e.g. ``/aw/atlassian/credentials``) take
priority over this catch-all due to FastAPI route ordering.

Auth: forwards the user's Bearer token (pass-through).
Error handling:
  - GET/HEAD requests: graceful degradation (503 → empty response with
    ``X-AW-Degraded: true`` header and ``degraded: true`` in body).
  - Write requests (POST/PUT/PATCH/DELETE): hard fail with 503.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from crewai_productfeature_planner.apis.agent_worker._client import (
    AgentWorkerError,
    request as aw_request,
)
from crewai_productfeature_planner.apis.agent_worker._config import (
    AGENT_WORKER_ENABLED,
)
from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/aw",
    tags=["Agent Worker"],
    dependencies=[Depends(require_sso_user)],
)

_READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _extract_bearer(request: Request) -> str:
    """Extract Bearer token from the request's Authorization header."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:]
    return ""


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    summary="Agent Worker proxy (catch-all)",
    description=(
        "Forwards any request to the Agent Worker service with the "
        "user's Bearer token. Specific /aw/atlassian/* routes take "
        "priority. GET requests degrade gracefully when Agent Worker "
        "is unavailable; write requests return 503."
    ),
)
async def proxy_to_agent_worker(
    path: str,
    request: Request,
    user: dict[str, Any] = Depends(require_sso_user),
) -> dict[str, Any]:
    if not AGENT_WORKER_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent Worker integration is not enabled",
        )

    method = request.method
    user_token = _extract_bearer(request)
    if not user_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required for Agent Worker proxy",
        )

    # Parse JSON body for non-GET requests.
    json_body: dict[str, Any] | None = None
    if method not in _READ_METHODS:
        try:
            body_bytes = await request.body()
            if body_bytes:
                import json
                json_body = json.loads(body_bytes)
        except Exception:
            pass  # Non-JSON body — forward without json_body

    aw_path = f"/{path}"
    is_read = method in _READ_METHODS

    try:
        result = await aw_request(
            method, aw_path, json_body=json_body, user_token=user_token,
        )
        logger.debug("[AgentWorker] Proxy %s %s → OK", method, aw_path)
        return result

    except AgentWorkerError as exc:
        if is_read and exc.status_code in (502, 503, 504):
            # Graceful degradation for reads.
            logger.warning(
                "[AgentWorker] Proxy %s %s degraded: %s", method, aw_path, exc,
            )
            return {
                "degraded": True,
                "message": "Agent Worker is temporarily unavailable",
                "status_code": exc.status_code,
            }

        # Write requests or non-transient errors: hard fail.
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
        ) from exc
