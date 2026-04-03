"""POST /health/slack-token/refresh — Force-refresh the Slack access token.

Request:  Optional query param ``team_id``. Requires SSO auth (Bearer).
Response: Refresh result with new token metadata.
Database: Invalidates cached token; ``get_valid_token()`` acquires and
          persists a fresh one via the stored refresh token in ``slackOAuth``.
"""

from fastapi import APIRouter, Depends, HTTPException

from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/health/slack-token/refresh",
    summary="Force-refresh the Slack access token",
    response_description="Refresh result with new token metadata",
    tags=["Health"],
    description=(
        "Invalidates the cached Slack access token and immediately acquires "
        "a fresh one using the stored refresh token.\n\n"
        "Use this after rotating credentials or when Slack API calls return "
        "``token_revoked`` / ``invalid_auth`` errors.\n\n"
        "Requires ``SLACK_CLIENT_ID``, ``SLACK_CLIENT_SECRET``, and a "
        "valid ``SLACK_REFRESH_TOKEN`` (obtained via the exchange endpoint "
        "or OAuth v2 callback)."
    ),
    responses={
        200: {
            "description": "Token refreshed successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Token refreshed successfully",
                        "token_type": "rotating",
                        "rotation_configured": True,
                        "expires_in_seconds": 43200,
                    }
                }
            },
        },
        400: {"description": "Refresh failed — check credentials and refresh token."},
    },
)
async def slack_token_refresh(team_id: str | None = None, user: dict = Depends(require_sso_user)) -> dict:
    """Force an immediate token refresh for *team_id*."""
    from crewai_productfeature_planner.mongodb.slack_oauth import get_all_teams
    from crewai_productfeature_planner.tools.slack_token_manager import (
        get_valid_token,
        invalidate,
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

    logger.info("[Health] POST /health/slack-token/refresh team_id=%s", team_id)
    invalidate(team_id)
    token = get_valid_token(team_id)
    if not token:
        logger.error("[Health] Token refresh failed team_id=%s", team_id)
        raise HTTPException(
            status_code=400,
            detail=f"Token refresh failed for team {team_id}",
        )

    logger.info("[Health] Token refreshed successfully team_id=%s", team_id)
    status = token_status(team_id)
    return {"message": "Token refreshed successfully", **status}
