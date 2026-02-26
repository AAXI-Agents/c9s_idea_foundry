"""Health check router."""

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get(
    "/health",
    tags=["Health"],
    summary="Health check",
    description=(
        "Returns a simple ``{\"status\": \"ok\"}`` payload to confirm the "
        "service is running.\n\n"
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
                    "example": {"status": "ok"}
                }
            },
        },
    },
)
async def health():
    """Basic liveness probe."""
    return {"status": "ok"}


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
async def slack_token_status() -> dict:
    """Return the current Slack token rotation state.

    Includes token type, whether rotation is configured, time until expiry,
    last refresh timestamp, and the path to the persisted token store.
    **No secrets are exposed.**
    """
    from crewai_productfeature_planner.tools.slack_token_manager import token_status

    return token_status()


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
        "| ``SLACK_CLIENT_SECRET`` | Slack app client secret |\n"
        "| ``SLACK_ACCESS_TOKEN`` | Existing long-lived ``xoxb-`` token |\n\n"
        "After a successful exchange, the new rotating access token, "
        "refresh token, and expiry are persisted to ``.slack_tokens.json`` "
        "and updated in the process environment.  Subsequent refreshes "
        "happen automatically.\n\n"
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
async def slack_token_exchange() -> dict:
    """One-time exchange of a long-lived ``xoxb-`` token for rotating tokens.

    Requires ``SLACK_CLIENT_ID``, ``SLACK_CLIENT_SECRET``, and
    ``SLACK_ACCESS_TOKEN`` to be set.
    """
    from crewai_productfeature_planner.tools.slack_token_manager import (
        exchange_token,
        token_status,
    )

    try:
        result = exchange_token()
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    status = token_status()
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
async def slack_token_refresh() -> dict:
    """Force an immediate token refresh."""
    from crewai_productfeature_planner.tools.slack_token_manager import (
        get_valid_token,
        invalidate,
        token_status,
    )

    invalidate()
    token = get_valid_token()
    if not token:
        raise HTTPException(
            status_code=400,
            detail="Token refresh failed — check SLACK_CLIENT_ID, "
                   "SLACK_CLIENT_SECRET, and SLACK_REFRESH_TOKEN",
        )

    status = token_status()
    return {"message": "Token refreshed successfully", **status}
