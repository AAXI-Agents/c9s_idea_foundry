"""User profile endpoints — merged SSO identity + local preferences."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.mongodb.user_preferences import (
    get_preferences,
    upsert_preferences,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/user",
    tags=["User Profile"],
    dependencies=[Depends(require_sso_user)],
)


# ── Models ────────────────────────────────────────────────────


class NotificationPreferences(BaseModel):
    """User notification channel preferences."""

    web: bool = Field(default=False, description="Receive web (in-app) notifications.")
    slack: bool = Field(default=True, description="Receive Slack notifications.")


class UserProfileResponse(BaseModel):
    """Merged user profile — SSO identity (read-only) + local prefs."""

    # SSO-managed (read-only)
    user_id: str = Field(..., description="SSO user ID (read-only).")
    email: str = Field(default="", description="SSO-managed email (read-only).")
    sso_display_name: str = Field(default="", description="Display name from SSO (read-only).")

    # Local preferences (editable)
    display_name: str | None = Field(default=None, description="Local display name override.")
    default_project_id: str | None = Field(default=None, description="Default project for new ideas.")
    timezone: str | None = Field(default=None, description="IANA timezone (e.g. 'Asia/Singapore').")
    notification_preferences: NotificationPreferences = Field(
        default_factory=NotificationPreferences,
        description="Notification channel preferences.",
    )


class UserProfileUpdateRequest(BaseModel):
    """Fields that can be updated via PATCH."""

    display_name: str | None = Field(default=None, description="Local display name override.")
    default_project_id: str | None = Field(default=None, description="Default project for new ideas.")
    timezone: str | None = Field(default=None, description="IANA timezone (e.g. 'Asia/Singapore').")
    notification_preferences: NotificationPreferences | None = Field(
        default=None, description="Notification channel preferences.",
    )


# ── Endpoints ─────────────────────────────────────────────────


@router.get(
    "/profile",
    summary="Get user profile",
    response_model=UserProfileResponse,
    description=(
        "Returns the merged user profile: SSO-managed identity fields "
        "(read-only) combined with user-editable local preferences."
    ),
    responses={200: {"description": "Profile returned successfully."}},
)
async def get_profile(user: dict = Depends(require_sso_user)):
    """Return merged SSO identity + local preferences."""
    user_id = user.get("user_id", "")
    logger.info("[UserProfile] GET profile for user_id=%s", user_id)

    prefs = get_preferences(user_id) or {}
    notif = prefs.get("notification_preferences") or {}

    return UserProfileResponse(
        user_id=user_id,
        email=user.get("email", ""),
        sso_display_name=user.get("display_name", ""),
        display_name=prefs.get("display_name"),
        default_project_id=prefs.get("default_project_id"),
        timezone=prefs.get("timezone"),
        notification_preferences=NotificationPreferences(
            web=notif.get("web", False),
            slack=notif.get("slack", True),
        ),
    )


@router.patch(
    "/profile",
    summary="Update user profile preferences",
    response_model=UserProfileResponse,
    description=(
        "Updates local user preferences. Only the fields provided in the "
        "request body are updated — omitted fields are left unchanged. "
        "SSO-managed fields (email, name, avatar) are not affected."
    ),
    responses={
        200: {"description": "Profile updated successfully."},
        500: {"description": "Failed to persist preferences."},
    },
)
async def update_profile(
    request: UserProfileUpdateRequest,
    user: dict = Depends(require_sso_user),
):
    """Update local preferences for the authenticated user."""
    user_id = user.get("user_id", "")
    logger.info("[UserProfile] PATCH profile for user_id=%s", user_id)

    updates: dict = {}
    if request.display_name is not None:
        updates["display_name"] = request.display_name
    if request.default_project_id is not None:
        updates["default_project_id"] = request.default_project_id
    if request.timezone is not None:
        updates["timezone"] = request.timezone
    if request.notification_preferences is not None:
        updates["notification_preferences"] = request.notification_preferences.model_dump()

    if not updates:
        # No fields to update — just return current profile
        return await get_profile(user)

    result = upsert_preferences(user_id, updates)
    if result is None:
        raise HTTPException(status_code=500, detail="Failed to persist preferences")

    notif = result.get("notification_preferences") or {}
    return UserProfileResponse(
        user_id=user_id,
        email=user.get("email", ""),
        sso_display_name=user.get("display_name", ""),
        display_name=result.get("display_name"),
        default_project_id=result.get("default_project_id"),
        timezone=result.get("timezone"),
        notification_preferences=NotificationPreferences(
            web=notif.get("web", False),
            slack=notif.get("slack", True),
        ),
    )
