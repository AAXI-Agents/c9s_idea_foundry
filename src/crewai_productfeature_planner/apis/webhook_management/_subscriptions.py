"""Webhook subscriptions endpoints.

GET    /webhook-subscriptions                     — list all
GET    /webhook-subscriptions/{key}               — Jira subscription detail
PATCH  /webhook-subscriptions/{key}               — toggle Jira status
POST   /webhook-subscriptions/github              — create GitHub webhook
GET    /webhook-subscriptions/github/{key}        — GitHub subscription detail
PATCH  /webhook-subscriptions/github/{key}        — toggle GitHub status
DELETE /webhook-subscriptions/github/{key}        — delete GitHub webhook
GET    /webhook-subscriptions/github/{key}/secret — reveal secret
POST   /webhook-subscriptions/github/{key}/regenerate-secret — regenerate secret
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from crewai_productfeature_planner.apis.admin_deps import require_enterprise_admin
from crewai_productfeature_planner.mongodb.webhook_subscriptions.repository import (
    add_github_repo,
    delete_webhook_subscription,
    get_webhook_subscription,
    list_webhook_subscriptions,
    regenerate_github_secret,
    remove_github_repo,
    reveal_github_secret,
    update_subscription_status,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/webhook-subscriptions",
    tags=["Webhooks"],
    dependencies=[Depends(require_enterprise_admin)],
)


# ── Models ────────────────────────────────────────────────────


class StatusPatchRequest(BaseModel):
    status: str = Field(..., pattern="^(active|paused)$")


class GitHubWebhookCreateRequest(BaseModel):
    project_key: str
    repo_owner: str
    repo_name: str


# ── List all subscriptions ────────────────────────────────────


@router.get(
    "",
    summary="List webhook subscriptions",
    description="List all webhook subscriptions for the enterprise.",
)
async def list_subscriptions(
    user: dict[str, Any] = Depends(require_enterprise_admin),
    status_filter: str | None = Query(None, alias="status"),
    provider: str | None = Query(None),
) -> list[dict[str, Any]]:
    enterprise_id = user.get("enterprise_id", "")
    logger.info(
        "[WebhookSubs] GET /webhook-subscriptions enterprise_id=%s provider=%s status=%s",
        enterprise_id,
        provider,
        status_filter,
    )
    return list_webhook_subscriptions(
        enterprise_id,
        provider=provider,
        status_filter=status_filter,
    )


# ── Jira subscription detail ─────────────────────────────────


@router.get(
    "/{jira_project_key}",
    summary="Get Jira subscription detail",
    description="Get the Jira webhook subscription for a specific project key.",
)
async def get_jira_subscription(
    jira_project_key: str,
    user: dict[str, Any] = Depends(require_enterprise_admin),
) -> dict[str, Any]:
    enterprise_id = user.get("enterprise_id", "")
    logger.info(
        "[WebhookSubs] GET /webhook-subscriptions/%s enterprise_id=%s",
        jira_project_key,
        enterprise_id,
    )
    sub = get_webhook_subscription(enterprise_id, "jira", project_key=jira_project_key)
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jira subscription not found.")
    return sub


# ── Toggle Jira status ────────────────────────────────────────


@router.patch(
    "/{jira_project_key}",
    summary="Toggle Jira subscription status",
    description="Pause or resume a Jira webhook subscription.",
)
async def toggle_jira_status(
    jira_project_key: str,
    body: StatusPatchRequest,
    user: dict[str, Any] = Depends(require_enterprise_admin),
) -> dict[str, Any]:
    enterprise_id = user.get("enterprise_id", "")
    logger.info(
        "[WebhookSubs] PATCH /webhook-subscriptions/%s status=%s enterprise_id=%s",
        jira_project_key,
        body.status,
        enterprise_id,
    )
    result = update_subscription_status(enterprise_id, "jira", body.status)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jira subscription not found.")
    return result


# ── GitHub: create webhook ────────────────────────────────────


@router.post(
    "/github",
    status_code=status.HTTP_201_CREATED,
    summary="Register a GitHub webhook",
    description="Register a new GitHub repo webhook for the enterprise.",
)
async def create_github_webhook(
    body: GitHubWebhookCreateRequest,
    user: dict[str, Any] = Depends(require_enterprise_admin),
) -> dict[str, Any]:
    enterprise_id = user.get("enterprise_id", "")
    organization_id = user.get("organization_id", "")
    logger.info(
        "[WebhookSubs] POST /webhook-subscriptions/github enterprise_id=%s repo=%s/%s",
        enterprise_id,
        body.repo_owner,
        body.repo_name,
    )

    base_url = os.environ.get("SERVER_BASE_URL", "http://localhost:8000").rstrip("/")
    repo_url = f"https://github.com/{body.repo_owner}/{body.repo_name}"
    github_settings_url = f"{repo_url}/settings/hooks"

    repo_entry = {
        "project_key": body.project_key,
        "repo_owner": body.repo_owner,
        "repo_name": body.repo_name,
        "repo_url": repo_url,
        "github_settings_url": github_settings_url,
        "github_webhook_id": None,
    }

    doc, secret = add_github_repo(
        enterprise_id,
        organization_id,
        repo_entry,
        webhook_url=f"{base_url}/webhooks/github",
    )

    response: dict[str, Any] = {"ok": True, "subscription": doc}
    if secret:
        response["webhook_secret"] = secret
    return response


# ── GitHub: get subscription detail ───────────────────────────


@router.get(
    "/github/{project_key}",
    summary="Get GitHub subscription detail",
    description="Get the GitHub webhook subscription for a specific project key.",
)
async def get_github_subscription(
    project_key: str,
    user: dict[str, Any] = Depends(require_enterprise_admin),
) -> dict[str, Any]:
    enterprise_id = user.get("enterprise_id", "")
    logger.info(
        "[WebhookSubs] GET /webhook-subscriptions/github/%s enterprise_id=%s",
        project_key,
        enterprise_id,
    )
    sub = get_webhook_subscription(enterprise_id, "github", project_key=project_key)
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GitHub subscription not found.")
    return sub


# ── GitHub: toggle status ─────────────────────────────────────


@router.patch(
    "/github/{project_key}",
    summary="Toggle GitHub subscription status",
    description="Pause or resume a GitHub webhook subscription.",
)
async def toggle_github_status(
    project_key: str,
    body: StatusPatchRequest,
    user: dict[str, Any] = Depends(require_enterprise_admin),
) -> dict[str, Any]:
    enterprise_id = user.get("enterprise_id", "")
    logger.info(
        "[WebhookSubs] PATCH /webhook-subscriptions/github/%s status=%s enterprise_id=%s",
        project_key,
        body.status,
        enterprise_id,
    )
    result = update_subscription_status(enterprise_id, "github", body.status, project_key=project_key)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GitHub subscription not found.")
    return result


# ── GitHub: delete webhook ────────────────────────────────────


@router.delete(
    "/github/{project_key}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete GitHub webhook",
    description="Remove a GitHub webhook registration for a specific project.",
)
async def delete_github_webhook(
    project_key: str,
    user: dict[str, Any] = Depends(require_enterprise_admin),
) -> None:
    enterprise_id = user.get("enterprise_id", "")
    logger.info(
        "[WebhookSubs] DELETE /webhook-subscriptions/github/%s enterprise_id=%s",
        project_key,
        enterprise_id,
    )
    success = delete_webhook_subscription(enterprise_id, "github", project_key=project_key)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GitHub subscription not found.")


# ── GitHub: reveal secret ─────────────────────────────────────


@router.get(
    "/github/{project_key}/secret",
    summary="Reveal GitHub webhook secret",
    description="Reveal the masked webhook secret for the GitHub subscription.",
)
async def get_github_secret(
    project_key: str,
    user: dict[str, Any] = Depends(require_enterprise_admin),
) -> dict[str, Any]:
    enterprise_id = user.get("enterprise_id", "")
    logger.info(
        "[WebhookSubs] GET /webhook-subscriptions/github/%s/secret enterprise_id=%s",
        project_key,
        enterprise_id,
    )
    secret = reveal_github_secret(enterprise_id)
    if not secret:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GitHub subscription not found or no secret set.")
    return {"ok": True, "webhook_secret": secret}


# ── GitHub: regenerate secret ─────────────────────────────────


@router.post(
    "/github/{project_key}/regenerate-secret",
    summary="Regenerate GitHub webhook secret",
    description="Generate a new webhook secret for the GitHub subscription.",
)
async def regenerate_github_webhook_secret(
    project_key: str,
    user: dict[str, Any] = Depends(require_enterprise_admin),
) -> dict[str, Any]:
    enterprise_id = user.get("enterprise_id", "")
    logger.info(
        "[WebhookSubs] POST /webhook-subscriptions/github/%s/regenerate-secret enterprise_id=%s",
        project_key,
        enterprise_id,
    )
    doc, new_secret = regenerate_github_secret(enterprise_id)
    if not doc or not new_secret:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GitHub subscription not found.")
    return {"ok": True, "subscription": doc, "webhook_secret": new_secret}
