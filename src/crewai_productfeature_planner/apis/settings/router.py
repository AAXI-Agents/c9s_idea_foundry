"""Enterprise settings router — GET and PATCH /settings.

GET is available to any authenticated user (read-only view of settings).
PATCH requires ENT_ADMIN or SYS_ADMIN role.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from crewai_productfeature_planner.apis.admin_deps import require_enterprise_admin
from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.mongodb.enterprise_settings import (
    get_enterprise_settings,
    update_enterprise_settings,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/settings",
    tags=["Settings"],
)


# ── Models ────────────────────────────────────────────────────────────────────


class AgentLabelMapping(BaseModel):
    jira_label: str
    agent_slug: str
    display_name: str
    description: str | None = None


class EnterpriseSettingsResponse(BaseModel):
    """Response wrapper for GET /settings."""

    settings: dict[str, Any] = Field(
        ..., description="Enterprise settings key-value document."
    )


class EnterpriseSettingsPatchRequest(BaseModel):
    """Partial-update request for PATCH /settings.

    All fields are optional — only provided fields are updated.
    """

    workspace_name: str | None = None
    log_level: str | None = None
    agent_toggles: dict[str, bool] | None = None
    agent_concurrency: int | None = Field(None, ge=1, le=20)
    agent_recommendations: int | None = Field(None, ge=1, le=10)
    agent_suggestions: int | None = Field(None, ge=1, le=10)
    agent_flow_iteration: int | None = Field(None, ge=1, le=3)
    enterprise_seat_capacity: int | None = Field(None, ge=1, le=1000)
    github_repo_enabled: bool | None = None
    agent_label_mappings: list[AgentLabelMapping] | None = None


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=EnterpriseSettingsResponse,
    summary="Get enterprise settings",
    description="Returns the enterprise settings for the authenticated user's enterprise.",
)
async def get_settings(
    user: dict[str, Any] = Depends(require_sso_user),
) -> EnterpriseSettingsResponse:
    enterprise_id = user.get("enterprise_id", "")
    if not enterprise_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No enterprise_id in token — cannot scope settings request.",
        )
    logger.info(
        "[Settings] GET /settings user_id=%s enterprise_id=%s",
        user.get("user_id"),
        enterprise_id,
    )
    settings = get_enterprise_settings(enterprise_id)
    return EnterpriseSettingsResponse(settings=settings)


@router.patch(
    "",
    response_model=EnterpriseSettingsResponse,
    summary="Update enterprise settings",
    description="Partially update enterprise settings. Requires ENT_ADMIN or SYS_ADMIN role.",
)
async def patch_settings(
    body: EnterpriseSettingsPatchRequest,
    user: dict[str, Any] = Depends(require_enterprise_admin),
) -> EnterpriseSettingsResponse:
    enterprise_id = user.get("enterprise_id", "")
    logger.info(
        "[Settings] PATCH /settings user_id=%s enterprise_id=%s",
        user.get("user_id"),
        enterprise_id,
    )

    # Only include fields that were explicitly set in the request
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No fields provided to update.",
        )

    # Validate log_level if provided
    if "log_level" in updates:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR"}
        if updates["log_level"].upper() not in valid_levels:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid log_level. Must be one of: {', '.join(sorted(valid_levels))}",
            )
        updates["log_level"] = updates["log_level"].upper()

    # Serialize agent_label_mappings to dicts for MongoDB
    if "agent_label_mappings" in updates and updates["agent_label_mappings"] is not None:
        updates["agent_label_mappings"] = [
            m.model_dump() if hasattr(m, "model_dump") else m
            for m in updates["agent_label_mappings"]
        ]

    settings = update_enterprise_settings(enterprise_id, updates)
    return EnterpriseSettingsResponse(settings=settings)
