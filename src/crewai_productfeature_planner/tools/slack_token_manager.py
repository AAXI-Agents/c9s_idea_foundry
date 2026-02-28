"""
Slack token rotation manager (team-scoped, MongoDB-backed).

Manages per-workspace bot tokens stored in the ``slackOAuth`` MongoDB
collection.  Each Slack team that installs the app gets its own token
record; the agent resolves the correct token by ``team_id``.

Implements Slack's configurable token rotation per the official docs:
https://docs.slack.dev/authentication/using-token-rotation

Lifecycle:
    1. **OAuth install** -- The OAuth callback stores the initial
       ``access_token`` and ``refresh_token`` in MongoDB via
       :func:`~crewai_productfeature_planner.mongodb.slack_oauth.upsert_team`.
    2. **Refresh** -- Before the 12-hour access token expires, call
       ``oauth.v2.access`` with ``grant_type=refresh_token`` and persist
       the fresh pair back to MongoDB.
    3. **Cache** -- Tokens are cached in-process per ``team_id`` so hot
       paths avoid hitting MongoDB on every Slack API call.

Required env vars (app-level, not team-level):
    SLACK_CLIENT_ID      -- App client ID
    SLACK_CLIENT_SECRET  -- App client secret
"""

from __future__ import annotations

import base64
import json
import logging
import os
import ssl
import threading
import time
import urllib.parse
import urllib.request
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_OAUTH_ACCESS_URL = "https://slack.com/api/oauth.v2.access"
_OAUTH_EXCHANGE_URL = "https://slack.com/api/oauth.v2.exchange"
_REFRESH_BUFFER_SECONDS = 300  # 5 minutes


# ---------------------------------------------------------------------------
# In-memory per-team cache
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_cache: dict[str, dict[str, Any]] = {}
# _cache[team_id] = {
#     "access_token": str,
#     "refresh_token": str | None,
#     "expires_at": float,
#     "last_refresh_at": float,
# }


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _basic_auth_header(client_id: str, client_secret: str) -> str:
    credentials = f"{client_id}:{client_secret}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


def _post_slack(url: str, client_id: str, client_secret: str, form_data: dict) -> dict:
    """POST to a Slack OAuth endpoint using HTTP Basic Auth."""
    data = urllib.parse.urlencode(form_data).encode()

    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("Authorization", _basic_auth_header(client_id, client_secret))

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
        raise RuntimeError(f"Slack OAuth HTTP request to {url} failed: {exc}") from exc

    if not body.get("ok"):
        error = body.get("error", "unknown_error")
        raise RuntimeError(f"Slack OAuth call to {url} failed: {error}")

    return body


# ---------------------------------------------------------------------------
# Refresh logic
# ---------------------------------------------------------------------------


def _do_refresh(client_id: str, client_secret: str, refresh_tok: str) -> dict:
    return _post_slack(
        _OAUTH_ACCESS_URL, client_id, client_secret,
        {"grant_type": "refresh_token", "refresh_token": refresh_tok},
    )


def _needs_refresh(entry: dict) -> bool:
    """Return ``True`` when the cached entry has expired or is about to."""
    if not entry.get("access_token"):
        return True
    return time.time() >= (entry.get("expires_at", 0.0) - _REFRESH_BUFFER_SECONDS)


def _is_rotating_token(token: str) -> bool:
    return token.startswith("xoxe.")


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _cache_entry(team_id: str) -> dict | None:
    """Return the in-memory cache entry for *team_id* (under lock)."""
    return _cache.get(team_id)


def _set_cache(
    team_id: str,
    access_token: str,
    refresh_token: str | None,
    expires_at: float,
) -> None:
    """Update the in-memory cache for *team_id* (caller must hold lock)."""
    _cache[team_id] = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at,
        "last_refresh_at": time.time(),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_valid_token(team_id: str | None = None) -> Optional[str]:
    """Return a valid Slack bot access token for *team_id*.

    Resolution order:

    1. In-memory cache (fast path).
    2. MongoDB ``slackOAuth`` collection.
    3. Token refresh via Slack API (if rotating token + client creds).
    4. ``None`` if no token is available.

    When *team_id* is ``None``, the function returns a token for the
    **sole** installed team if exactly one exists -- this maintains
    backwards compatibility for single-workspace deployments and
    non-event code paths that have no team context.
    """
    from crewai_productfeature_planner.mongodb.slack_oauth.repository import (
        get_all_teams,
        get_team,
        update_tokens,
    )

    client_id = os.environ.get("SLACK_CLIENT_ID", "").strip()
    client_secret = os.environ.get("SLACK_CLIENT_SECRET", "").strip()
    rotation_configured = bool(client_id and client_secret)

    # -- Resolve team_id when not provided --
    if not team_id:
        teams = get_all_teams()
        if len(teams) == 1:
            team_id = teams[0]["team_id"]
        elif len(teams) == 0:
            logger.warning(
                "[TokenManager] No teams in slackOAuth -- "
                "install the app via OAuth first"
            )
            return None
        else:
            logger.warning(
                "[TokenManager] Multiple teams installed but no team_id "
                "provided -- cannot determine which token to use"
            )
            return None

    with _lock:
        # 1. Check in-memory cache
        entry = _cache_entry(team_id)
        if entry and not _needs_refresh(entry):
            return entry["access_token"]

        # 2. Load from MongoDB
        doc = get_team(team_id)
        if not doc:
            logger.warning(
                "[TokenManager] No OAuth record for team=%s", team_id,
            )
            return None

        access_token = doc.get("access_token", "")
        refresh_token = doc.get("refresh_token")
        expires_at = doc.get("expires_at", 0.0)

        # If DB token is still valid, cache and return
        if access_token and time.time() < (expires_at - _REFRESH_BUFFER_SECONDS):
            _set_cache(team_id, access_token, refresh_token, expires_at)
            logger.info(
                "[TokenManager] Loaded token for team=%s from MongoDB (valid)",
                team_id,
            )
            return access_token

        # 3. Attempt token refresh
        if rotation_configured and refresh_token:
            try:
                result = _do_refresh(client_id, client_secret, refresh_token)
                new_access = result["access_token"]
                new_refresh = result.get("refresh_token", refresh_token)
                new_expires_in = result.get("expires_in", 43200)

                # Persist to MongoDB
                update_tokens(
                    team_id=team_id,
                    access_token=new_access,
                    refresh_token=new_refresh,
                    expires_in=new_expires_in,
                )

                # Update in-memory cache
                new_expires_at = time.time() + new_expires_in
                _set_cache(team_id, new_access, new_refresh, new_expires_at)

                logger.info(
                    "[TokenManager] Token refreshed for team=%s (expires in %ds)",
                    team_id,
                    new_expires_in,
                )
                return new_access
            except RuntimeError as exc:
                err_msg = str(exc).lower()
                if "invalid_refresh_token" in err_msg:
                    logger.error(
                        "[TokenManager] Refresh token invalid for team=%s. "
                        "Re-install the app to obtain a new token.",
                        team_id,
                    )
                else:
                    logger.error(
                        "[TokenManager] Token refresh failed for team=%s: %s",
                        team_id,
                        exc,
                    )

        # 4. Return the (possibly expired) token as a last resort
        if access_token:
            logger.warning(
                "[TokenManager] Using potentially expired token for team=%s",
                team_id,
            )
            _set_cache(
                team_id,
                access_token,
                refresh_token,
                time.time() + 300,   # short TTL so we retry soon
            )
            return access_token

    return None


def invalidate(team_id: str | None = None) -> None:
    """Evict cached tokens so the next call re-reads from MongoDB.

    If *team_id* is ``None``, **all** cached entries are cleared.
    """
    with _lock:
        if team_id:
            _cache.pop(team_id, None)
            logger.info("[TokenManager] Cache invalidated for team=%s", team_id)
        else:
            _cache.clear()
            logger.info("[TokenManager] Full token cache invalidated")


def token_status(team_id: str) -> dict:
    """Return diagnostic info about the token state for *team_id*."""
    from crewai_productfeature_planner.mongodb.slack_oauth.repository import (
        token_status as _db_token_status,
    )
    return _db_token_status(team_id)


# ---------------------------------------------------------------------------
# Exchange logic (one-time: long-lived -> rotating)
# ---------------------------------------------------------------------------


def exchange_token(
    team_id: str,
    *,
    client_id: str | None = None,
    client_secret: str | None = None,
    token: str | None = None,
) -> dict:
    """Exchange a long-lived token for a rotating access + refresh token pair.

    The new pair is persisted to MongoDB under *team_id*.
    """
    from crewai_productfeature_planner.mongodb.slack_oauth.repository import (
        update_tokens,
    )

    client_id = client_id or os.environ.get("SLACK_CLIENT_ID", "").strip()
    client_secret = client_secret or os.environ.get("SLACK_CLIENT_SECRET", "").strip()

    if not all([client_id, client_secret, token]):
        raise ValueError(
            "exchange_token requires SLACK_CLIENT_ID, SLACK_CLIENT_SECRET, "
            "and a token to exchange"
        )

    result = _post_slack(
        _OAUTH_EXCHANGE_URL, client_id, client_secret, {"token": token},
    )

    new_access = result["access_token"]
    new_refresh = result["refresh_token"]
    expires_in = result.get("expires_in", 43200)

    # Persist to MongoDB
    update_tokens(
        team_id=team_id,
        access_token=new_access,
        refresh_token=new_refresh,
        expires_in=expires_in,
    )

    # Update cache
    with _lock:
        _set_cache(
            team_id,
            new_access,
            new_refresh,
            time.time() + expires_in,
        )

    logger.info(
        "[TokenManager] Token exchanged for team=%s (expires in %ds)",
        team_id,
        expires_in,
    )
    return result
