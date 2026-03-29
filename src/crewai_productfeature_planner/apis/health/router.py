"""Health check router."""

from fastapi import APIRouter, Depends, HTTPException

from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.scripts.logging_config import get_logger
from crewai_productfeature_planner.version import (
    get_codex,
    get_latest_codex_entry,
    get_version,
)

logger = get_logger(__name__)

router = APIRouter()


@router.get(
    "/health",
    tags=["Health"],
    summary="Health check",
    description=(
        "Returns ``{\"status\": \"ok\", \"version\": \"X.Y.Z\"}`` to confirm the "
        "service is running and which build is deployed.\n\n"
        "Use this as a **liveness probe** for container orchestration "
        "(Docker, Kubernetes) or uptime monitoring.  The endpoint performs "
        "no database or external service checks — use "
        "``GET /health/slack-token`` to verify Slack token health."
    ),
    responses={
        200: {
            "description": "Service is alive.",
            "content": {
                "application/json": {
                    "example": {"status": "ok", "version": "0.1.3"}
                }
            },
        },
    },
)
async def health():
    """Basic liveness probe."""
    return {"status": "ok", "version": get_version()}


@router.get(
    "/version",
    tags=["Health"],
    summary="Application version and codex",
    description=(
        "Returns the current application version, the latest changelog "
        "entry, and the full codex (changelog) of all iterations.\n\n"
        "Use this to verify which build is deployed and trace what "
        "changed in each iteration."
    ),
    responses={
        200: {
            "description": "Version info with codex.",
            "content": {
                "application/json": {
                    "example": {
                        "version": "0.1.3",
                        "latest": {
                            "version": "0.1.3",
                            "date": "2026-02-28",
                            "summary": "Version control & codex.",
                        },
                        "codex": [
                            {
                                "version": "0.1.0",
                                "date": "2026-02-14",
                                "summary": "Initial release.",
                            },
                        ],
                    }
                }
            },
        },
    },
)
async def version():
    """Return version and full codex (changelog)."""
    return {
        "version": get_version(),
        "latest": get_latest_codex_entry(),
        "codex": get_codex(),
    }


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
