"""Integrations router — check connection status and manage Slack.

Reads credentials from MongoDB (per-tenant) first, then falls back to
environment variables for backwards compatibility.

Slack endpoints:
    POST /integrations/slack/connect  — return OAuth install URL
    DELETE /integrations/slack        — revoke at Slack + delete from DB
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.mongodb._tenant import TenantContext
from crewai_productfeature_planner.mongodb.integration_credentials import (
    get_credentials,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/integrations",
    tags=["Integrations"],
    dependencies=[Depends(require_sso_user)],
)


# ── Response models ───────────────────────────────────────────


class IntegrationDetail(BaseModel):
    """Status of a single integration."""

    configured: bool = Field(
        ..., description="Whether all required credentials are set."
    )
    base_url: str = Field(
        default="", description="The base URL of the service (masked)."
    )
    project_key: str = Field(
        default="", description="Project key (Jira only)."
    )


class IntegrationStatusResponse(BaseModel):
    """Response for GET /integrations/status."""

    confluence: IntegrationDetail = Field(
        ..., description="Confluence integration status."
    )
    jira: IntegrationDetail = Field(
        ..., description="Jira integration status."
    )
    slack: IntegrationDetail = Field(
        ..., description="Slack integration status."
    )


class SlackConnectResponse(BaseModel):
    """Response for POST /integrations/slack/connect."""

    install_url: str = Field(
        ..., description="Slack OAuth install URL to open in a popup/tab."
    )


# ── Helpers ───────────────────────────────────────────────────


def _mask_url(raw: str) -> str:
    """Return scheme + hostname only (mask path / credentials)."""
    if not raw:
        return ""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(raw)
        return f"{parsed.scheme}://{parsed.hostname}"
    except Exception:  # noqa: BLE001
        return "(configured)"


def _resolve_atlassian_creds(user: dict[str, Any]) -> dict[str, str]:
    """Return Atlassian credentials — MongoDB first, env-var fallback.

    Returns a dict with keys: ``base_url``, ``username``, ``api_token``,
    ``confluence_base_url``, ``jira_project_key`` (all strings, may be empty).
    """
    org_id = user.get("organization_id", "")
    result = {
        "base_url": "",
        "username": "",
        "api_token": "",
        "confluence_base_url": "",
        "jira_project_key": "",
    }

    # Try MongoDB first.
    if org_id:
        tenant = TenantContext.from_user(user)
        doc = get_credentials(org_id, "atlassian", tenant=tenant)
        if doc and doc.get("credentials"):
            creds = doc["credentials"]
            result["base_url"] = creds.get("base_url", "")
            result["username"] = creds.get("username", "")
            result["api_token"] = creds.get("api_token", "")
            result["confluence_base_url"] = doc.get("confluence_base_url", "")
            result["jira_project_key"] = doc.get("jira_project_key", "")
            logger.debug(
                "[Integrations] Loaded Atlassian creds from MongoDB for org_id=%s",
                org_id,
            )
            return result

    # Fallback to environment variables.
    result["base_url"] = os.environ.get("ATLASSIAN_BASE_URL", "")
    result["username"] = os.environ.get("ATLASSIAN_USERNAME", "")
    result["api_token"] = os.environ.get("ATLASSIAN_API_TOKEN", "")
    result["jira_project_key"] = os.environ.get("JIRA_PROJECT_KEY", "")
    return result


# ── Endpoint ──────────────────────────────────────────────────


@router.get(
    "/status",
    summary="Check integration connection status",
    response_model=IntegrationStatusResponse,
    description=(
        "Returns the configuration status of Confluence and Jira "
        "integrations.  Reads from per-tenant MongoDB storage first, "
        "falls back to environment variables."
    ),
    responses={200: {"description": "Integration status returned."}},
)
async def get_integration_status(
    user: dict = Depends(require_sso_user),
):
    """Check which integrations are configured."""
    creds = _resolve_atlassian_creds(user)

    base_url = creds["base_url"]
    username = creds["username"]
    api_token = creds["api_token"]
    jira_key = creds["jira_project_key"]
    confluence_url = creds["confluence_base_url"] or base_url

    confluence_ok = bool(base_url and username and api_token)
    jira_ok = bool(base_url and username and api_token and jira_key)

    masked_url = _mask_url(base_url)
    masked_confluence = _mask_url(confluence_url) if confluence_url != base_url else masked_url

    # Slack status — check if any team is installed for this tenant.
    slack_detail = _resolve_slack_status(user)

    return IntegrationStatusResponse(
        confluence=IntegrationDetail(
            configured=confluence_ok,
            base_url=masked_confluence if confluence_ok else "",
        ),
        jira=IntegrationDetail(
            configured=jira_ok,
            base_url=masked_url if jira_ok else "",
            project_key=jira_key if jira_ok else "",
        ),
        slack=slack_detail,
    )


# ── Slack helpers ─────────────────────────────────────────────


def _resolve_slack_status(user: dict[str, Any]) -> IntegrationDetail:
    """Check whether Slack OAuth tokens exist for this tenant."""
    try:
        tenant = TenantContext.from_user(user)
        from crewai_productfeature_planner.mongodb.slack_oauth import get_all_teams

        teams = get_all_teams(tenant=tenant)
        if teams:
            first = teams[0]
            team_name = first.get("team_name", "")
            return IntegrationDetail(
                configured=True,
                base_url=f"slack://{team_name}" if team_name else "slack://connected",
            )
    except Exception:
        logger.debug("[Integrations] Slack status check failed", exc_info=True)

    return IntegrationDetail(configured=False)


def _build_slack_install_url(user: dict[str, Any]) -> str:
    """Build a Slack OAuth install URL with signed state."""
    from crewai_productfeature_planner.apis.slack.oauth_router import (
        sign_install_state,
    )

    client_id = os.environ.get("SLACK_CLIENT_ID", "").strip()
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Slack integration is not configured (SLACK_CLIENT_ID missing)",
        )

    scopes = os.environ.get(
        "SLACK_BOT_SCOPES",
        "app_mentions:read,chat:write,commands,im:history,im:read,im:write",
    ).strip()

    redirect_uri = os.environ.get("SLACK_REDIRECT_URI", "").strip()

    tenant = TenantContext.from_user(user)
    state_token = sign_install_state(tenant)

    import urllib.parse

    params = {
        "client_id": client_id,
        "scope": scopes,
        "state": state_token,
    }
    if redirect_uri:
        params["redirect_uri"] = redirect_uri

    return f"https://slack.com/oauth/v2/authorize?{urllib.parse.urlencode(params)}"


# ── Slack endpoints ───────────────────────────────────────────


@router.post(
    "/slack/connect",
    status_code=status.HTTP_200_OK,
    response_model=SlackConnectResponse,
    summary="Get Slack OAuth install URL",
    description=(
        "Returns a Slack OAuth install URL that the frontend opens in a "
        "popup or new tab. The signed state token carries the tenant "
        "context so the callback stores tokens under the correct tenant."
    ),
)
async def slack_connect(
    user: dict = Depends(require_sso_user),
) -> SlackConnectResponse:
    url = _build_slack_install_url(user)
    logger.info(
        "[Integrations] Slack connect URL generated for user_id=%s",
        user.get("user_id", "?"),
    )
    return SlackConnectResponse(install_url=url)


@router.delete(
    "/slack",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disconnect Slack integration",
    description=(
        "Revokes the Slack bot token and deletes the OAuth record from "
        "MongoDB. If Slack revocation fails, the local record is still "
        "deleted and a warning is logged."
    ),
)
async def slack_disconnect(
    user: dict = Depends(require_sso_user),
) -> None:
    tenant = TenantContext.from_user(user)

    from crewai_productfeature_planner.mongodb.slack_oauth import (
        delete_team,
        get_all_teams,
    )

    teams = get_all_teams(tenant=tenant)
    if not teams:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Slack integration found for this organization",
        )

    for team_doc in teams:
        team_id = team_doc.get("team_id", "")
        access_token = team_doc.get("access_token", "")

        # Attempt to revoke at Slack first.
        if access_token:
            try:
                _revoke_slack_token(access_token)
                logger.info(
                    "[Integrations] Slack token revoked for team=%s", team_id,
                )
            except Exception:
                logger.warning(
                    "[Integrations] Slack token revocation failed for team=%s "
                    "(will delete locally anyway)",
                    team_id,
                    exc_info=True,
                )

        # Delete from MongoDB.
        delete_team(team_id)

    # Invalidate token manager cache.
    try:
        from crewai_productfeature_planner.tools.slack_token_manager import invalidate
        invalidate()
    except Exception:
        pass

    logger.info(
        "[Integrations] Slack disconnected for user_id=%s, teams=%d",
        user.get("user_id", "?"),
        len(teams),
    )


def _revoke_slack_token(token: str) -> None:
    """Call Slack's auth.revoke API to invalidate a token."""
    import ssl
    import urllib.request

    url = "https://slack.com/api/auth.revoke"
    req = urllib.request.Request(url, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    ssl_ctx: ssl.SSLContext | None = None
    try:
        import certifi
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass

    with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as resp:
        import json
        body = json.loads(resp.read().decode())
        if not body.get("ok") and body.get("error") != "token_revoked":
            logger.warning(
                "[Integrations] Slack auth.revoke returned error: %s",
                body.get("error", "unknown"),
            )
