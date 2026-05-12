"""Atlassian credential proxy routes — ``/aw/atlassian/credentials``.

Implements store-and-forward: credentials are saved locally in MongoDB
(encrypted at rest) and then forwarded to Agent Worker.

Endpoints:
    POST   /aw/atlassian/credentials             — upsert & sync
    POST   /aw/atlassian/credentials/{org_id}/test — test via Agent Worker
    DELETE /aw/atlassian/credentials/{org_id}     — delete local + Agent Worker
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, status

from crewai_productfeature_planner.apis.agent_worker._client import (
    AgentWorkerError,
    request as aw_request,
)
from crewai_productfeature_planner.apis.agent_worker._config import (
    AGENT_WORKER_ENABLED,
)
from crewai_productfeature_planner.apis.agent_worker._models import (
    AtlassianCredentialRequest,
    AtlassianCredentialStatusResponse,
    AtlassianCredentialTestResult,
)
from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.mongodb._tenant import TenantContext
from crewai_productfeature_planner.mongodb.integration_credentials import (
    delete_credentials,
    get_credentials,
    upsert_credentials,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/aw/atlassian", tags=["Agent Worker"])


# ── POST /aw/atlassian/credentials ──────────────────────────────


@router.post(
    "/credentials",
    status_code=status.HTTP_201_CREATED,
    response_model=AtlassianCredentialStatusResponse,
    summary="Upsert Atlassian credentials",
    description=(
        "Save Atlassian credentials locally (encrypted at rest) and "
        "forward to Agent Worker.  Idempotent — re-posting overwrites."
    ),
)
async def upsert_atlassian_credentials(
    body: AtlassianCredentialRequest,
    user: dict[str, Any] = Depends(require_sso_user),
) -> AtlassianCredentialStatusResponse:
    org_id = body.organization_id or user.get("organization_id", "")
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="organization_id is required (from body or SSO token)",
        )

    tenant = TenantContext.from_user({
        **user,
        "organization_id": org_id,
    })

    # Store locally (encrypted).
    creds_dict = {
        "base_url": body.jira_base_url,
        "username": body.jira_email,
        "api_token": body.jira_api_token,
    }
    saved_doc = upsert_credentials(
        organization_id=org_id,
        provider="atlassian",
        credentials=creds_dict,
        user_id=user.get("user_id", ""),
        confluence_base_url=body.confluence_base_url,
        synced_to_agent_worker=False,
        tenant=tenant,
    )
    if saved_doc is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save credentials locally",
        )

    # Forward to Agent Worker (best-effort).
    synced = False
    message = "Credentials saved locally."
    if AGENT_WORKER_ENABLED:
        try:
            aw_payload = body.to_agent_worker_payload()
            await aw_request("POST", "/atlassian/credentials", json_body=aw_payload)
            synced = True
            message = "Credentials saved and synced to Agent Worker."
            logger.info(
                "[AgentWorker] Synced Atlassian credentials for org_id=%s", org_id,
            )
        except AgentWorkerError as exc:
            logger.warning(
                "[AgentWorker] Forward failed for org_id=%s: %s", org_id, exc,
            )
            message = (
                f"Credentials saved locally but Agent Worker sync failed: {exc.detail}"
            )
    else:
        message = "Credentials saved locally (Agent Worker not enabled)."

    # Update sync status in DB.
    if synced:
        from crewai_productfeature_planner.mongodb.integration_credentials import (
            mark_synced,
        )
        mark_synced(org_id, "atlassian", tenant=tenant)

    return AtlassianCredentialStatusResponse(
        saved=True,
        synced_to_agent_worker=synced,
        message=message,
    )


# ── POST /aw/atlassian/credentials/{org_id}/test ────────────────


@router.post(
    "/credentials/{org_id}/test",
    response_model=AtlassianCredentialTestResult,
    summary="Test Atlassian credentials",
    description=(
        "Forward a test request to Agent Worker to verify the stored "
        "Atlassian credentials are valid."
    ),
)
async def test_atlassian_credentials(
    org_id: str = Path(..., description="Organization ID"),
    user: dict[str, Any] = Depends(require_sso_user),
) -> AtlassianCredentialTestResult:
    if not AGENT_WORKER_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent Worker integration is not enabled",
        )

    try:
        result = await aw_request(
            "POST", f"/atlassian/credentials/{org_id}/test",
        )
        return AtlassianCredentialTestResult(
            success=result.get("success", False),
            message=result.get("message", ""),
            jira_valid=result.get("jira_valid", False),
            confluence_valid=result.get("confluence_valid", False),
        )
    except AgentWorkerError as exc:
        logger.warning(
            "[AgentWorker] Test credentials failed for org_id=%s: %s", org_id, exc,
        )
        return AtlassianCredentialTestResult(
            success=False,
            message=f"Agent Worker error: {exc.detail}",
        )


# ── DELETE /aw/atlassian/credentials/{org_id} ───────────────────


@router.delete(
    "/credentials/{org_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Atlassian credentials",
    description=(
        "Remove Atlassian credentials from both local storage and "
        "Agent Worker."
    ),
)
async def delete_atlassian_credentials(
    org_id: str = Path(..., description="Organization ID"),
    user: dict[str, Any] = Depends(require_sso_user),
) -> dict[str, Any]:
    tenant = TenantContext.from_user({
        **user,
        "organization_id": org_id,
    })

    # Delete locally.
    local_deleted = delete_credentials(org_id, "atlassian", tenant=tenant)

    # Delete from Agent Worker (best-effort).
    aw_deleted = False
    aw_message = ""
    if AGENT_WORKER_ENABLED:
        try:
            await aw_request("DELETE", f"/atlassian/credentials/{org_id}")
            aw_deleted = True
        except AgentWorkerError as exc:
            aw_message = f"Agent Worker delete failed: {exc.detail}"
            logger.warning(
                "[AgentWorker] Delete credentials failed for org_id=%s: %s",
                org_id, exc,
            )

    return {
        "deleted": local_deleted or aw_deleted,
        "local_deleted": local_deleted,
        "agent_worker_deleted": aw_deleted,
        "message": aw_message or "Credentials deleted.",
    }
