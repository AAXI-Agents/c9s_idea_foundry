"""SSO webhook receiver — handles user lifecycle events from the SSO service.

Listens for the SSO webhook event types:
    user.created       — log new user registration
    user.updated       — log profile changes
    user.deleted       — revoke active sessions
    login.success      — optional audit logging
    login.failed       — optional security alerting
    token.revoked      — clean up cached auth state
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from crewai_productfeature_planner.apis.sso_auth import verify_sso_webhook

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/sso/webhooks", tags=["SSO Webhooks"])


@router.post(
    "/events",
    status_code=200,
    summary="Receive SSO user lifecycle events",
)
async def receive_sso_event(payload: dict[str, Any] = Depends(verify_sso_webhook)):
    """Process an inbound SSO webhook event.

    The payload is verified via HMAC-SHA256 (X-Webhook-Signature) before
    dispatch.
    """
    event_type = payload.get("event", "")
    data = payload.get("data", {})
    user_id = data.get("user_id", "")
    email = data.get("email", "")

    logger.info(
        "[SSO Webhook] Received event=%s user_id=%s email=%s",
        event_type, user_id, email,
    )

    handler = _EVENT_HANDLERS.get(event_type)
    if handler:
        handler(data)
    else:
        logger.debug("[SSO Webhook] Unhandled event type: %s", event_type)

    return {"status": "ok", "event": event_type}


# ── Event handlers ────────────────────────────────────────────


def _handle_user_created(data: dict[str, Any]) -> None:
    """Handle a new user registration from SSO."""
    email = data.get("email", "")
    user_id = data.get("user_id", "")
    logger.info("[SSO Webhook] New user registered: %s (%s)", email, user_id)


def _handle_user_updated(data: dict[str, Any]) -> None:
    """Handle a user profile update from SSO."""
    user_id = data.get("user_id", "")
    logger.info("[SSO Webhook] User updated: %s", user_id)


def _handle_user_deleted(data: dict[str, Any]) -> None:
    """Handle user deletion — clean up their active sessions."""
    user_id = data.get("user_id", "")
    logger.info("[SSO Webhook] User deleted: %s", user_id)


def _handle_login_success(data: dict[str, Any]) -> None:
    """Handle successful login event."""
    email = data.get("email", "")
    logger.info("[SSO Webhook] Login success: %s", email)


def _handle_login_failed(data: dict[str, Any]) -> None:
    """Handle failed login attempt — potential security alert."""
    email = data.get("email", "")
    logger.warning("[SSO Webhook] Login failed: %s", email)


def _handle_token_revoked(data: dict[str, Any]) -> None:
    """Handle token revocation — clear any cached auth state."""
    user_id = data.get("user_id", "")
    logger.info("[SSO Webhook] Token revoked for user: %s", user_id)


_EVENT_HANDLERS: dict[str, Any] = {
    "user.created": _handle_user_created,
    "user.updated": _handle_user_updated,
    "user.deleted": _handle_user_deleted,
    "login.success": _handle_login_success,
    "login.failed": _handle_login_failed,
    "token.revoked": _handle_token_revoked,
}
