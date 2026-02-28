"""CRUD operations for the ``slackOAuth`` MongoDB collection.

Each document is keyed by ``team_id`` (Slack workspace ID).  The collection
stores the bot access token, refresh token, scopes, and metadata so the
agent can authenticate as the correct bot for each installed workspace.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from pymongo import ReturnDocument
from pymongo.errors import PyMongoError

from crewai_productfeature_planner.mongodb.client import get_db
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

SLACK_OAUTH_COLLECTION = "slackOAuth"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── write ─────────────────────────────────────────────────────


def upsert_team(
    *,
    team_id: str,
    team_name: str = "",
    access_token: str,
    refresh_token: str | None = None,
    token_type: str = "bot",
    scope: str = "",
    bot_user_id: str = "",
    app_id: str = "",
    expires_in: int | None = None,
    authed_user_id: str | None = None,
) -> dict[str, Any] | None:
    """Insert or replace the OAuth record for *team_id*.

    Called after a successful OAuth code exchange (app installation or
    reinstallation).

    Returns:
        The upserted document on success, or ``None`` on failure.
    """
    now = _now_iso()
    expires_at = time.time() + expires_in if expires_in else time.time() + 86400

    doc: dict[str, Any] = {
        "team_id": team_id,
        "team_name": team_name,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": token_type,
        "scope": scope,
        "bot_user_id": bot_user_id,
        "app_id": app_id,
        "expires_at": expires_at,
        "updated_at": now,
        "authed_user_id": authed_user_id,
    }

    try:
        result = get_db()[SLACK_OAUTH_COLLECTION].find_one_and_update(
            {"team_id": team_id},
            {
                "$set": doc,
                "$setOnInsert": {"installed_at": now},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        logger.info(
            "[SlackOAuth] Upserted team=%s (%s) bot_user=%s",
            team_id,
            team_name,
            bot_user_id,
        )
        return result
    except PyMongoError as exc:
        logger.error(
            "[SlackOAuth] Failed to upsert team=%s: %s",
            team_id,
            exc,
        )
        return None


def update_tokens(
    *,
    team_id: str,
    access_token: str,
    refresh_token: str | None = None,
    expires_in: int | None = None,
) -> bool:
    """Update only the token fields after a refresh cycle.

    Returns ``True`` on success, ``False`` on failure or unknown team.
    """
    now = _now_iso()
    update_fields: dict[str, Any] = {
        "access_token": access_token,
        "updated_at": now,
    }
    if refresh_token is not None:
        update_fields["refresh_token"] = refresh_token
    if expires_in is not None:
        update_fields["expires_at"] = time.time() + expires_in
    else:
        update_fields["expires_at"] = time.time() + 86400

    try:
        result = get_db()[SLACK_OAUTH_COLLECTION].update_one(
            {"team_id": team_id},
            {"$set": update_fields},
        )
        if result.matched_count == 0:
            logger.warning(
                "[SlackOAuth] update_tokens: team=%s not found", team_id,
            )
            return False
        logger.debug("[SlackOAuth] Tokens refreshed for team=%s", team_id)
        return True
    except PyMongoError as exc:
        logger.error(
            "[SlackOAuth] Failed to update tokens for team=%s: %s",
            team_id,
            exc,
        )
        return False


# ── read ──────────────────────────────────────────────────────


def get_team(team_id: str) -> dict[str, Any] | None:
    """Return the OAuth document for *team_id*, or ``None`` if not found."""
    try:
        doc = get_db()[SLACK_OAUTH_COLLECTION].find_one({"team_id": team_id})
        return doc
    except PyMongoError as exc:
        logger.error(
            "[SlackOAuth] Failed to read team=%s: %s",
            team_id,
            exc,
        )
        return None


def get_all_teams() -> list[dict[str, Any]]:
    """Return all installed team OAuth records.

    Useful for multi-workspace diagnostics.
    """
    try:
        return list(get_db()[SLACK_OAUTH_COLLECTION].find({}))
    except PyMongoError as exc:
        logger.error("[SlackOAuth] Failed to list teams: %s", exc)
        return []


def token_status(team_id: str) -> dict[str, Any]:
    """Return diagnostic info for *team_id* (no secrets exposed)."""
    doc = get_team(team_id)
    if not doc:
        return {
            "team_id": team_id,
            "installed": False,
        }

    access = doc.get("access_token", "")
    is_rotating = access.startswith("xoxe.")
    expires_at = doc.get("expires_at", 0.0)

    if access.startswith("xoxe.xoxb-"):
        token_type = "rotating_bot"
    elif access.startswith("xoxe.xoxp-"):
        token_type = "rotating_user"
    elif access.startswith("xoxb-"):
        token_type = "static_bot"
    elif access.startswith("xoxp-"):
        token_type = "static_user"
    else:
        token_type = "unknown"

    return {
        "team_id": team_id,
        "team_name": doc.get("team_name", ""),
        "installed": True,
        "token_type": token_type,
        "is_rotating": is_rotating,
        "has_refresh_token": bool(doc.get("refresh_token")),
        "expires_at": expires_at,
        "expires_in_seconds": max(0, int(expires_at - time.time())),
        "bot_user_id": doc.get("bot_user_id", ""),
        "updated_at": doc.get("updated_at", ""),
        "installed_at": doc.get("installed_at", ""),
    }


# ── delete ────────────────────────────────────────────────────


def delete_team(team_id: str) -> bool:
    """Remove the OAuth record for *team_id*.

    Returns ``True`` if a document was deleted.
    """
    try:
        result = get_db()[SLACK_OAUTH_COLLECTION].delete_one({"team_id": team_id})
        deleted = result.deleted_count > 0
        if deleted:
            logger.info("[SlackOAuth] Deleted team=%s", team_id)
        return deleted
    except PyMongoError as exc:
        logger.error(
            "[SlackOAuth] Failed to delete team=%s: %s",
            team_id,
            exc,
        )
        return False
