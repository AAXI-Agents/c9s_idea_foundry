"""POST /health/slack-token/exchange — Exchange long-lived token for rotating.

Request:  Optional query param ``team_id``. Requires SSO auth (Bearer).
Response: Exchange result with new token metadata.
Database: Reads existing token from ``slackOAuth`` collection;
          ``exchange_token()`` persists new rotating credentials back.
"""

from fastapi import APIRouter, Depends, HTTPException

from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/health/slack-token/exchange",
    summary="Exchange long-lived Slack token for rotating tokens",
    response_description="Exchange result with new token metadata",
    tags=["Health"],
    description=(
        "One-time exchange of a long-lived ``xoxb-`` bot token for rotating "
        "tokens via Slack's ``tooling.tokens.rotate`` API.\n\n"
        "**Required environment variables:**\n\n"
        "| Variable | Description |\n"
        "|---|---|\n"
        "| ``SLACK_CLIENT_ID`` | Slack app client ID |\n"
        "| ``SLACK_CLIENT_SECRET`` | Slack app client secret |\n\n"
        "The existing ``xoxb-`` token is read from the MongoDB "
        "``slackOAuth`` collection for the given ``team_id``.\n\n"
        "After a successful exchange, the new rotating access token, "
        "refresh token, and expiry are persisted to the ``slackOAuth`` "
        "collection.  Subsequent refreshes happen automatically.\n\n"
        "**Note:** This is a one-time operation. Once exchanged, use "
        "``POST /health/slack-token/refresh`` to force a manual refresh."
    ),
    responses={
        200: {
            "description": "Token exchanged successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "token_type": "rotating",
                        "rotation_configured": True,
                        "expires_in": 43200,
                        "message": "Token exchanged successfully",
                        "scope": "chat:write,channels:read",
                    }
                }
            },
        },
        400: {"description": "Missing required env vars or exchange failed."},
    },
)
async def slack_token_exchange(team_id: str | None = None, user: dict = Depends(require_sso_user)) -> dict:
    """One-time exchange of a long-lived ``xoxb-`` token for rotating tokens.

    Requires ``SLACK_CLIENT_ID`` and ``SLACK_CLIENT_SECRET`` env vars.
    The *team_id* determines which installed workspace's token to exchange.
    """
    from crewai_productfeature_planner.mongodb.slack_oauth import (
        get_all_teams,
        get_team,
    )
    from crewai_productfeature_planner.tools.slack_token_manager import (
        exchange_token,
        token_status,
    )

    if not team_id:
        teams = get_all_teams()
        if len(teams) == 1:
            team_id = teams[0]["team_id"]
        else:
            raise HTTPException(
                status_code=400,
                detail="team_id is required (multiple or no teams installed)",
            )

    logger.info("[Health] POST /health/slack-token/exchange team_id=%s", team_id)

    # Read the existing long-lived token from MongoDB for the exchange
    doc = get_team(team_id)
    existing_token = doc.get("access_token", "") if doc else ""
    if not existing_token:
        logger.warning("[Health] No existing token for team_id=%s", team_id)
        raise HTTPException(
            status_code=400,
            detail=f"No existing token found for team {team_id}",
        )

    try:
        result = exchange_token(team_id, token=existing_token)
    except (ValueError, RuntimeError) as exc:
        logger.error("[Health] Token exchange failed team_id=%s", team_id, exc_info=True)
        raise HTTPException(status_code=400, detail="Token exchange failed. Check server logs.")

    logger.info("[Health] Token exchanged successfully team_id=%s", team_id)
    status = token_status(team_id)
    return {
        **status,
        "message": "Token exchanged successfully",
        "token_type": result.get("token_type", "bot"),
        "expires_in": result.get("expires_in", 43200),
        "scope": result.get("scope", ""),
    }
