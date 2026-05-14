"""GET /webhook-config — credential status and webhook URLs per provider."""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from crewai_productfeature_planner.apis.admin_deps import require_enterprise_admin
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/webhook-config",
    tags=["Webhooks"],
    dependencies=[Depends(require_enterprise_admin)],
)


# ── Models ────────────────────────────────────────────────────


class ProviderStatus(BaseModel):
    available: bool
    webhook_url: str = ""


class JiraProviderStatus(ProviderStatus):
    credential_status: str = Field(
        default="missing",
        description="missing | invalid | valid",
    )


class GitHubProviderStatus(ProviderStatus):
    env_pat_configured: bool = False
    requires_sys_admin: bool = True


class WebhookConfigResponse(BaseModel):
    ok: bool = True
    jira: JiraProviderStatus
    github: GitHubProviderStatus


# ── Endpoint ──────────────────────────────────────────────────


@router.get(
    "",
    response_model=WebhookConfigResponse,
    summary="Get webhook configuration status",
    description="Returns credential status and webhook URLs for each provider.",
)
async def get_webhook_config(
    user: dict[str, Any] = Depends(require_enterprise_admin),
) -> WebhookConfigResponse:
    enterprise_id = user.get("enterprise_id", "")
    logger.info(
        "[WebhookConfig] GET /webhook-config user_id=%s enterprise_id=%s",
        user.get("user_id"),
        enterprise_id,
    )

    # Determine server base URL for webhook endpoints
    base_url = os.environ.get("SERVER_BASE_URL", "http://localhost:8000").rstrip("/")

    # Check Jira credentials
    jira_status = "missing"
    jira_available = False
    try:
        from crewai_productfeature_planner.mongodb._tenant import TenantContext
        from crewai_productfeature_planner.mongodb.integration_credentials import (
            get_credentials,
        )

        ctx = TenantContext(
            enterprise_id=enterprise_id,
            organization_id=user.get("organization_id", ""),
            role=None,
        )
        creds = get_credentials("atlassian", ctx=ctx)
        if creds:
            jira_status = "valid"
            jira_available = True
        else:
            jira_status = "missing"
    except Exception:
        jira_status = "missing"

    # Check GitHub PAT configuration
    github_pat_configured = bool(os.environ.get("GITHUB_PAT") or os.environ.get("GITHUB_TOKEN"))

    return WebhookConfigResponse(
        ok=True,
        jira=JiraProviderStatus(
            available=jira_available,
            webhook_url=f"{base_url}/webhooks/jira",
            credential_status=jira_status,
        ),
        github=GitHubProviderStatus(
            available=github_pat_configured,
            webhook_url=f"{base_url}/webhooks/github",
            env_pat_configured=github_pat_configured,
            requires_sys_admin=True,
        ),
    )
