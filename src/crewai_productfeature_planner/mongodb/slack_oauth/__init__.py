"""Repository for the ``slackOAuth`` collection.

Stores per-team Slack bot OAuth tokens so the agent uses the correct
credentials for each workspace that has installed the app.

Standard document schema
------------------------
::

    {
        "team_id":          str,              # Slack workspace / team ID (primary key)
        "team_name":        str,              # human-readable workspace name
        "access_token":     str,              # bot ``xoxb-`` or rotating ``xoxe.xoxb-`` token
        "refresh_token":    str | None,       # single-use refresh token (rotating tokens)
        "token_type":       str,              # e.g. "bot"
        "scope":            str,              # comma-separated OAuth scopes
        "bot_user_id":      str,              # bot's Slack user ID
        "app_id":           str,              # Slack app ID
        "expires_at":       float,            # UTC epoch when access_token expires
        "installed_at":     str (ISO-8601),   # first install timestamp
        "updated_at":       str (ISO-8601),   # last token refresh / re-install
        "authed_user_id":   str | None,       # installing user's ID
    }
"""

from crewai_productfeature_planner.mongodb.slack_oauth.repository import (
    SLACK_OAUTH_COLLECTION,
    delete_team,
    get_all_teams,
    get_team,
    refresh_tokens_cas,
    token_status,
    upsert_team,
    update_tokens,
)

__all__ = [
    "SLACK_OAUTH_COLLECTION",
    "delete_team",
    "get_all_teams",
    "get_team",
    "refresh_tokens_cas",
    "token_status",
    "upsert_team",
    "update_tokens",
]
