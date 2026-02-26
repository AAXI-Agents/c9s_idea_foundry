"""Health check router."""

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get(
    "/health",
    tags=["Health"],
    summary="Health check",
    description="Returns a simple ok payload to confirm the service is running.",
)
async def health():
    """Basic liveness probe."""
    return {"status": "ok"}


@router.get(
    "/health/slack-token",
    summary="Slack token rotation status",
    response_description="Token rotation diagnostics (no secrets exposed)",
    tags=["Health"],
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
    responses={
        400: {"description": "Missing required env vars or exchange failed"},
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
    responses={
        400: {"description": "Refresh failed"},
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
