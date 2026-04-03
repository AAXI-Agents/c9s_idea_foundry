"""GET /health/slack-token — Slack token rotation diagnostics.

Request:  Optional query param ``team_id``.
Response: Token rotation metadata (no secrets exposed).
Database: Reads from ``slackOAuth`` collection via ``mongodb.slack_oauth``.
"""

from fastapi import APIRouter

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get(
    "/health/slack-token",
    summary="Slack token rotation status",
    response_description="Token rotation diagnostics (no secrets exposed)",
    tags=["Health"],
    description=(
        "Returns the current Slack token rotation state including token "
        "type, whether rotation is configured, time until expiry, last "
        "refresh timestamp, and the path to the persisted token store.\n\n"
        "**No secrets are exposed** — only metadata about token health.\n\n"
        "Useful for monitoring dashboards to detect token expiry before "
        "Slack API calls start failing."
    ),
    responses={
        200: {
            "description": "Token rotation diagnostics.",
            "content": {
                "application/json": {
                    "example": {
                        "token_type": "rotating",
                        "rotation_configured": True,
                        "expires_in_seconds": 39600,
                        "last_refresh": "2026-02-25T10:00:00Z",
                        "store_path": ".slack_tokens.json",
                    }
                }
            },
        },
    },
)
async def slack_token_status(team_id: str | None = None) -> dict:
    """Return the current Slack token rotation state.

    Includes token type, whether rotation is configured, time until expiry,
    and last refresh timestamp.  **No secrets are exposed.**

    When ``team_id`` is omitted and exactly one team is installed the
    status of that team is returned automatically.
    """
    from crewai_productfeature_planner.mongodb.slack_oauth import (
        get_all_teams,
        token_status,
    )

    logger.info("[Health] GET /health/slack-token team_id=%s", team_id)

    if not team_id:
        teams = get_all_teams()
        if len(teams) == 1:
            team_id = teams[0]["team_id"]
        elif len(teams) == 0:
            logger.info("[Health] No Slack teams installed")
            return {"installed": False, "message": "No teams installed"}
        else:
            logger.info("[Health] Multiple teams installed: %s", [t["team_id"] for t in teams])
            return {
                "installed": True,
                "teams": [t["team_id"] for t in teams],
                "message": "Multiple teams installed — pass team_id",
            }

    status = token_status(team_id)
    logger.info("[Health] Token status for team_id=%s: type=%s", team_id, status.get("token_type", "unknown"))
    return status
