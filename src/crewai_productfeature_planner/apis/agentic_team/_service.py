"""Outbound API client for querying Agentic Team status.

Uses SSO client_credentials service token for authentication.
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx

from crewai_productfeature_planner.apis.agentic_team._config import (
    AGENTIC_TEAM_BASE_URL,
    AGENTIC_TEAM_ENABLED,
    IDEA_FOUNDRY_BASE_URL,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# Cache service token (short-lived — refreshed on 401)
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
        logger.warning("[AgenticTeam] SSO credentials not configured for service token")
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
                    "audience": "c9s_agentic_team",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                _cached_token = data.get("access_token", "")
                return _cached_token or ""
            logger.warning(
                "[AgenticTeam] Service token request failed: %d", resp.status_code,
            )
    except httpx.RequestError as exc:
        logger.error("[AgenticTeam] Service token request error: %s", exc)

    return ""


def _invalidate_token() -> None:
    """Clear cached token (e.g. on 401 response)."""
    global _cached_token  # noqa: PLW0603
    _cached_token = None


async def get_project_features(project_key: str) -> dict[str, Any] | None:
    """Query Agentic Team for project feature/ticket status."""
    if not AGENTIC_TEAM_ENABLED or not AGENTIC_TEAM_BASE_URL:
        return None

    token = await _get_service_token()
    url = f"{AGENTIC_TEAM_BASE_URL}/projects/{project_key}/features"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 401:
                _invalidate_token()
                return None
            if resp.status_code == 200:
                return resp.json()
            logger.debug(
                "[AgenticTeam] GET %s → %d", url, resp.status_code,
            )
    except httpx.RequestError as exc:
        logger.warning("[AgenticTeam] Request failed: %s %s", url, exc)

    return None


async def get_task_status(issue_key: str) -> dict[str, Any] | None:
    """Query Agentic Team for a single task's pipeline status."""
    if not AGENTIC_TEAM_ENABLED or not AGENTIC_TEAM_BASE_URL:
        return None

    token = await _get_service_token()
    url = f"{AGENTIC_TEAM_BASE_URL}/tasks/{issue_key}"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 401:
                _invalidate_token()
                return None
            if resp.status_code == 200:
                return resp.json()
    except httpx.RequestError as exc:
        logger.warning("[AgenticTeam] Request failed: %s %s", url, exc)

    return None


async def get_pipeline_dashboard() -> dict[str, Any] | None:
    """Query Agentic Team pipeline dashboard overview."""
    if not AGENTIC_TEAM_ENABLED or not AGENTIC_TEAM_BASE_URL:
        return None

    token = await _get_service_token()
    url = f"{AGENTIC_TEAM_BASE_URL}/pipeline/dashboard"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 401:
                _invalidate_token()
                return None
            if resp.status_code == 200:
                return resp.json()
    except httpx.RequestError as exc:
        logger.warning("[AgenticTeam] Request failed: %s %s", url, exc)

    return None


async def kickoff_pipeline(
    project_key: str,
    epic_keys: list[str],
    idea_id: str | None = None,
    priority: str = "medium",
) -> dict[str, Any] | None:
    """Trigger Agentic Team to start working on specified epics.

    Phase 3 feature — auto-triggers agent pipeline after Jira ticket creation.
    """
    if not AGENTIC_TEAM_ENABLED or not AGENTIC_TEAM_BASE_URL:
        return None

    token = await _get_service_token()
    url = f"{AGENTIC_TEAM_BASE_URL}/pipeline/kickoff"

    # Build callback URL for Agentic Team to notify us on completion
    callback_url = (
        f"{IDEA_FOUNDRY_BASE_URL}/webhooks/agentic-team"
        if IDEA_FOUNDRY_BASE_URL
        else None
    )

    payload: dict[str, Any] = {
        "project_key": project_key,
        "epic_keys": epic_keys,
        "priority": priority,
        "source": "idea_foundry",
        "idea_id": idea_id,
    }
    if callback_url:
        payload["callback_url"] = callback_url

    idempotency_key = str(uuid.uuid4())

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Idempotency-Key": idempotency_key,
                },
            )
            if resp.status_code == 401:
                _invalidate_token()
                return None
            if resp.status_code in (200, 202):
                logger.info(
                    "[AgenticTeam] Pipeline kickoff accepted: project=%s epics=%s",
                    project_key, epic_keys,
                )
                return resp.json()
            logger.warning(
                "[AgenticTeam] Pipeline kickoff failed: %d %s",
                resp.status_code, resp.text[:200],
            )
    except httpx.RequestError as exc:
        logger.error("[AgenticTeam] Kickoff request failed: %s", exc)

    return None


async def batch_kickoff_pipeline(
    tasks: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Trigger Agentic Team batch pipeline for multiple Jira sub-tasks.

    Each task dict must have:
      - issue_key: The Jira issue key (e.g. "PRD-42")
      - task_input: Description of what the agent should implement
      - topic: Short topic label
      - labels: List of labels for tracing (e.g. ["idea:<id>", "feature:<name>"])

    Returns:
        Response dict with ``accepted``, ``skipped``, ``errors`` counts,
        or ``None`` on failure.
    """
    if not AGENTIC_TEAM_ENABLED or not AGENTIC_TEAM_BASE_URL:
        return None

    if not tasks:
        logger.debug("[AgenticTeam] batch_kickoff_pipeline called with empty tasks")
        return None

    token = await _get_service_token()
    url = f"{AGENTIC_TEAM_BASE_URL}/pipeline/batch-kickoff"

    # Include callback URL so Agentic Team knows where to send events
    callback_url = (
        f"{IDEA_FOUNDRY_BASE_URL}/webhooks/agentic-team"
        if IDEA_FOUNDRY_BASE_URL
        else None
    )

    payload: dict[str, Any] = {"tasks": tasks}
    if callback_url:
        payload["callback_url"] = callback_url

    idempotency_key = str(uuid.uuid4())

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Idempotency-Key": idempotency_key,
                },
            )
            if resp.status_code == 401:
                _invalidate_token()
                token = await _get_service_token()
                if not token:
                    return None
                resp = await client.post(
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Idempotency-Key": idempotency_key,
                    },
                )
            if resp.status_code in (200, 202):
                result = resp.json()
                logger.info(
                    "[AgenticTeam] Batch kickoff accepted: %d tasks, accepted=%s skipped=%s errors=%s",
                    len(tasks),
                    result.get("accepted"),
                    result.get("skipped"),
                    result.get("errors"),
                )
                return result
            logger.warning(
                "[AgenticTeam] Batch kickoff failed: %d %s",
                resp.status_code, resp.text[:200],
            )
    except httpx.RequestError as exc:
        logger.error("[AgenticTeam] Batch kickoff request failed: %s", exc)

    return None


async def get_idea_agent_status(idea_id: str) -> dict[str, Any] | None:
    """Query Agentic Team for all pipeline tasks related to an idea.

    Returns aggregated status: per-task progress, overall completion %,
    and any failures.
    """
    if not AGENTIC_TEAM_ENABLED or not AGENTIC_TEAM_BASE_URL:
        return None

    token = await _get_service_token()
    url = f"{AGENTIC_TEAM_BASE_URL}/pipeline/status"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                url,
                params={"label": f"idea:{idea_id}"},
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 401:
                _invalidate_token()
                return None
            if resp.status_code == 200:
                return resp.json()
            logger.debug(
                "[AgenticTeam] GET %s → %d", url, resp.status_code,
            )
    except httpx.RequestError as exc:
        logger.warning("[AgenticTeam] Status request failed: %s %s", url, exc)

    return None
