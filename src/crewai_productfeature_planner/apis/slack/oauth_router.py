"""Slack OAuth callback router.

Handles the ``/slack/oauth/callback`` redirect from Slack's OAuth v2 flow
(app installation / reinstallation).  Exchanges the authorization ``code``
for bot and user tokens via ``oauth.v2.access``, persists them, and updates
the in-memory environment.

Redirect URL (must match the manifest):
    https://<ngrok-domain>/slack/oauth/callback
"""

from __future__ import annotations

import base64
import json
import logging
import os
import ssl
import urllib.parse
import urllib.request

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Slack OAuth"])

_OAUTH_V2_ACCESS_URL = "https://slack.com/api/oauth.v2.access"


def _exchange_code(code: str, redirect_uri: str | None = None) -> dict:
    """Exchange an OAuth authorization code for tokens via ``oauth.v2.access``."""
    client_id = os.environ.get("SLACK_CLIENT_ID", "").strip()
    client_secret = os.environ.get("SLACK_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        raise RuntimeError(
            "SLACK_CLIENT_ID and SLACK_CLIENT_SECRET must be set to "
            "complete the OAuth callback"
        )

    form: dict[str, str] = {"code": code}
    if redirect_uri:
        form["redirect_uri"] = redirect_uri

    data = urllib.parse.urlencode(form).encode()
    creds = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    req = urllib.request.Request(_OAUTH_V2_ACCESS_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("Authorization", f"Basic {creds}")

    ssl_ctx: ssl.SSLContext | None = None
    try:
        import certifi
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass

    try:
        with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as resp:
            body = json.loads(resp.read().decode())
    except Exception as exc:
        raise RuntimeError(f"oauth.v2.access HTTP request failed: {exc}") from exc

    if not body.get("ok"):
        error = body.get("error", "unknown_error")
        raise RuntimeError(f"oauth.v2.access failed: {error}")

    return body


def _apply_tokens(result: dict) -> dict:
    """Persist exchanged tokens to MongoDB ``slackOAuth`` and return a summary."""
    from crewai_productfeature_planner.mongodb.slack_oauth import upsert_team
    from crewai_productfeature_planner.tools.slack_token_manager import invalidate

    summary: dict = {}

    bot_access = result.get("access_token", "")
    if bot_access:
        summary["bot_token_prefix"] = bot_access[:12] + "…"
        summary["bot_token_type"] = (
            "rotating" if bot_access.startswith("xoxe.") else "static"
        )

    bot_refresh = result.get("refresh_token", "")
    if bot_refresh:
        summary["has_bot_refresh"] = True

    expires_in = result.get("expires_in")
    if expires_in:
        summary["bot_expires_in"] = expires_in

    authed_user = result.get("authed_user", {})
    user_access = authed_user.get("access_token", "")
    if user_access:
        summary["user_token_prefix"] = user_access[:12] + "…"
    user_refresh = authed_user.get("refresh_token", "")
    if user_refresh:
        summary["has_user_refresh"] = True

    team_id = result.get("team", {}).get("id", "")
    team_name = result.get("team", {}).get("name", "")
    scope = result.get("scope", "")
    bot_user_id = result.get("bot_user_id", "")
    app_id = result.get("app_id", "")
    token_type = result.get("token_type", "")

    summary["team"] = team_name
    summary["team_id"] = team_id
    summary["scope"] = scope
    summary["bot_user_id"] = bot_user_id
    summary["app_id"] = app_id
    summary["token_type"] = token_type

    # ── Persist to MongoDB (replaces env-var / .env / .slack_tokens.json) ──
    if team_id and bot_access:
        try:
            doc = upsert_team(
                team_id=team_id,
                team_name=team_name,
                access_token=bot_access,
                refresh_token=bot_refresh or None,
                token_type=token_type,
                scope=scope,
                bot_user_id=bot_user_id,
                app_id=app_id,
                expires_in=expires_in,
                authed_user_id=authed_user.get("id"),
            )
            summary["persisted"] = doc is not None

            # Invalidate the in-memory cache so the next API call picks
            # up the freshly-stored token.
            invalidate(team_id)
        except Exception as exc:
            logger.error("Failed to persist OAuth tokens to MongoDB: %s", exc)
            summary["persisted"] = False
    else:
        logger.warning(
            "OAuth callback missing team_id or access_token — tokens NOT persisted"
        )
        summary["persisted"] = False

    return summary


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get(
    "/slack/oauth/callback",
    response_class=HTMLResponse,
    tags=["Slack OAuth"],
    summary="Slack OAuth v2 callback",
    response_description="HTML page confirming app installation",
    description=(
        "Handles the Slack OAuth v2 redirect after a user clicks **Install** "
        "or **Reinstall** on the Slack app management page.\n\n"
        "**Flow:**\n\n"
        "1. Slack redirects to this URL with a ``code`` query parameter.\n"
        "2. The server exchanges the ``code`` for bot and user tokens via "
        "``oauth.v2.access`` using HTTP Basic auth (client ID + secret).\n"
        "3. Tokens are persisted to the ``slackOAuth`` MongoDB collection, "
        "keyed by ``team_id`` (Slack workspace ID).  Each installing "
        "workspace gets its own token record.\n"
        "4. A confirmation HTML page is returned to the user's browser.\n\n"
        "**Required environment variables:**\n\n"
        "| Variable | Description |\n"
        "|---|---|\n"
        "| ``SLACK_CLIENT_ID`` | Slack app client ID |\n"
        "| ``SLACK_CLIENT_SECRET`` | Slack app client secret |\n\n"
        "**Redirect URL** (must match the manifest):\n"
        "``https://<ngrok-domain>/slack/oauth/callback``\n\n"
        "If the ``code`` exchange fails or Slack passes an ``error`` "
        "parameter, an error HTML page is returned with HTTP 400."
    ),
    responses={
        200: {
            "description": "App installed successfully — HTML confirmation page.",
            "content": {
                "text/html": {
                    "example": "<html><body><h1>✔ Slack App Installed Successfully</h1>...</body></html>"
                }
            },
        },
        400: {
            "description": (
                "OAuth error, missing authorization code, or token exchange failure. "
                "Returns an HTML error page with the specific error message."
            ),
        },
    },
)
async def slack_oauth_callback(request: Request) -> HTMLResponse:
    """Handle the Slack OAuth v2 redirect after app installation."""
    params = request.query_params

    if "error" in params:
        error = params["error"]
        logger.warning("Slack OAuth callback received error: %s", error)
        return HTMLResponse(
            content=(
                f"<html><body>"
                f"<h1>Slack App Installation Failed</h1>"
                f"<p>Error: <code>{error}</code></p>"
                f"<p>Go back to <a href='https://api.slack.com/apps'>Slack Apps</a> "
                f"and try again.</p>"
                f"</body></html>"
            ),
            status_code=400,
        )

    code = params.get("code", "").strip()
    if not code:
        return HTMLResponse(
            content=(
                "<html><body>"
                "<h1>Missing Authorization Code</h1>"
                "<p>No <code>code</code> parameter received from Slack.</p>"
                "</body></html>"
            ),
            status_code=400,
        )

    redirect_uri = str(request.url).split("?")[0]

    try:
        result = _exchange_code(code, redirect_uri=redirect_uri)
    except RuntimeError as exc:
        logger.error("OAuth code exchange failed: %s", exc)
        return HTMLResponse(
            content=(
                f"<html><body>"
                f"<h1>Token Exchange Failed</h1>"
                f"<p>{exc}</p>"
                f"</body></html>"
            ),
            status_code=400,
        )

    summary = _apply_tokens(result)
    logger.info("Slack app installed/reinstalled: %s", summary)

    team = summary.get("team", "your workspace")
    scopes = summary.get("scope", "N/A")
    bot_user = summary.get("bot_user_id", "N/A")
    token_type = summary.get("bot_token_type", "unknown")

    return HTMLResponse(
        content=(
            f"<html><body style='font-family: sans-serif; max-width: 600px; margin: 40px auto;'>"
            f"<h1>&#10004; Slack App Installed Successfully</h1>"
            f"<table style='border-collapse: collapse;'>"
            f"<tr><td style='padding: 4px 12px; font-weight: bold;'>Team</td>"
            f"<td style='padding: 4px 12px;'>{team}</td></tr>"
            f"<tr><td style='padding: 4px 12px; font-weight: bold;'>Bot User ID</td>"
            f"<td style='padding: 4px 12px;'><code>{bot_user}</code></td></tr>"
            f"<tr><td style='padding: 4px 12px; font-weight: bold;'>Token Type</td>"
            f"<td style='padding: 4px 12px;'>{token_type}</td></tr>"
            f"<tr><td style='padding: 4px 12px; font-weight: bold;'>Scopes</td>"
            f"<td style='padding: 4px 12px;'><code>{scopes}</code></td></tr>"
            f"</table>"
            f"<p style='margin-top: 20px; color: #666;'>"
            f"Tokens have been saved. The server is ready to use.</p>"
            f"</body></html>"
        ),
        status_code=200,
    )
