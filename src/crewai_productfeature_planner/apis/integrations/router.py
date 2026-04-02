"""Integrations router — check connection status for Confluence and Jira."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from crewai_productfeature_planner.apis.sso_auth import require_sso_user
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


# ── Endpoint ──────────────────────────────────────────────────


@router.get(
    "/status",
    summary="Check integration connection status",
    response_model=IntegrationStatusResponse,
    description=(
        "Returns the configuration status of Confluence and Jira "
        "integrations. Checks whether the required environment "
        "variables are set — does not test connectivity."
    ),
    responses={200: {"description": "Integration status returned."}},
)
async def get_integration_status(
    user: dict = Depends(require_sso_user),
):
    """Check which integrations are configured."""
    base_url = os.environ.get("ATLASSIAN_BASE_URL", "")
    username = os.environ.get("ATLASSIAN_USERNAME", "")
    api_token = os.environ.get("ATLASSIAN_API_TOKEN", "")
    jira_key = os.environ.get("JIRA_PROJECT_KEY", "")

    confluence_ok = bool(base_url and username and api_token)
    jira_ok = bool(base_url and username and api_token and jira_key)

    # Mask the base URL for safety (show domain only)
    masked_url = ""
    if base_url:
        try:
            from urllib.parse import urlparse

            parsed = urlparse(base_url)
            masked_url = f"{parsed.scheme}://{parsed.hostname}"
        except Exception:  # noqa: BLE001
            masked_url = "(configured)"

    return IntegrationStatusResponse(
        confluence=IntegrationDetail(
            configured=confluence_ok,
            base_url=masked_url if confluence_ok else "",
        ),
        jira=IntegrationDetail(
            configured=jira_ok,
            base_url=masked_url if jira_ok else "",
            project_key=jira_key if jira_ok else "",
        ),
    )
