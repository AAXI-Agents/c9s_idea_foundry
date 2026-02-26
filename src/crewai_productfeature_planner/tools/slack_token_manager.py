"""
Slack token rotation manager.

Implements Slack's configurable token rotation per the official docs:
https://docs.slack.dev/authentication/using-token-rotation

Lifecycle:
    1. **Initial exchange** – Convert a long-lived ``xoxb-``/``xoxp-`` token
       into a rotating ``xoxe.xoxb-``/``xoxe.xoxp-`` access token + a
       single-use refresh token via ``oauth.v2.exchange``.
    2. **Refresh** – Before the 12-hour access token expires, call
       ``oauth.v2.access`` with ``grant_type=refresh_token``.
    3. **Persist** – Both tokens are written to ``.slack_tokens.json``
       so they survive process restarts.

Required env vars for rotation:
    SLACK_CLIENT_ID      – App client ID
    SLACK_CLIENT_SECRET  – App client secret
    SLACK_REFRESH_TOKEN  – Current refresh token

Optional:
    SLACK_ACCESS_TOKEN   – Seed access token
    SLACK_TOKEN_STORE    – Path to JSON file for persisting tokens
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
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Token env-var helpers
# ---------------------------------------------------------------------------

_TOKEN_ENV = "SLACK_ACCESS_TOKEN"


def _get_token_env() -> str:
    return os.environ.get(_TOKEN_ENV, "").strip()


def _set_token_env(token: str) -> None:
    os.environ[_TOKEN_ENV] = token


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_OAUTH_ACCESS_URL = "https://slack.com/api/oauth.v2.access"
_OAUTH_EXCHANGE_URL = "https://slack.com/api/oauth.v2.exchange"
_REFRESH_BUFFER_SECONDS = 300  # 5 minutes

_DEFAULT_TOKEN_STORE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    ".slack_tokens.json",
)

# ---------------------------------------------------------------------------
# Module-level state (singleton)
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_access_token: Optional[str] = None
_refresh_token: Optional[str] = None
_expires_at: float = 0.0
_last_refresh_at: float = 0.0


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def _token_store_path() -> str:
    return os.environ.get("SLACK_TOKEN_STORE", _DEFAULT_TOKEN_STORE)


def _load_persisted_tokens() -> dict:
    path = _token_store_path()
    try:
        if os.path.exists(path):
            with open(path, "r") as fh:
                data = json.load(fh)
                logger.debug("Loaded persisted Slack tokens from %s", path)
                return data
    except Exception as exc:
        logger.warning("Could not load Slack token store %s: %s", path, exc)
    return {}


def _persist_tokens(
    access_token: str,
    refresh_token: str,
    expires_at: float,
) -> None:
    path = _token_store_path()
    payload = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at,
        "last_refresh_at": time.time(),
    }
    try:
        with open(path, "w") as fh:
            json.dump(payload, fh, indent=2)
        os.chmod(path, 0o600)
        logger.debug("Persisted Slack tokens to %s", path)
    except Exception as exc:
        logger.warning("Could not persist Slack tokens to %s: %s", path, exc)


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
# Exchange logic (one-time: long-lived → rotating)
# ---------------------------------------------------------------------------

def exchange_token(
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    token: Optional[str] = None,
) -> dict:
    """Exchange a long-lived token for a rotating access + refresh token pair."""
    global _access_token, _refresh_token, _expires_at, _last_refresh_at

    client_id = client_id or os.environ.get("SLACK_CLIENT_ID", "").strip()
    client_secret = client_secret or os.environ.get("SLACK_CLIENT_SECRET", "").strip()
    token = token or _get_token_env()

    if not all([client_id, client_secret, token]):
        raise ValueError(
            "exchange_token requires SLACK_CLIENT_ID, SLACK_CLIENT_SECRET, "
            "and SLACK_ACCESS_TOKEN (or explicit arguments)"
        )

    result = _post_slack(_OAUTH_EXCHANGE_URL, client_id, client_secret, {"token": token})

    new_access = result["access_token"]
    new_refresh = result["refresh_token"]
    expires_in = result.get("expires_in", 43200)

    with _lock:
        _access_token = new_access
        _refresh_token = new_refresh
        _expires_at = time.time() + expires_in
        _last_refresh_at = time.time()

    _set_token_env(new_access)
    os.environ["SLACK_REFRESH_TOKEN"] = new_refresh
    _persist_tokens(new_access, new_refresh, _expires_at)

    logger.info(
        "Slack token exchanged successfully (expires in %ds, prefix: %s)",
        expires_in, new_access[:10] + "…",
    )
    return result


# ---------------------------------------------------------------------------
# Refresh logic
# ---------------------------------------------------------------------------

def _do_refresh(client_id: str, client_secret: str, refresh_tok: str) -> dict:
    return _post_slack(
        _OAUTH_ACCESS_URL, client_id, client_secret,
        {"grant_type": "refresh_token", "refresh_token": refresh_tok},
    )


def _needs_refresh() -> bool:
    if not _access_token:
        return True
    return time.time() >= (_expires_at - _REFRESH_BUFFER_SECONDS)


def _is_rotating_token(token: str) -> bool:
    return token.startswith("xoxe.")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_valid_token() -> Optional[str]:
    """Return a valid Slack access token, refreshing if necessary."""
    global _access_token, _refresh_token, _expires_at, _last_refresh_at

    client_id = os.environ.get("SLACK_CLIENT_ID", "").strip()
    client_secret = os.environ.get("SLACK_CLIENT_SECRET", "").strip()
    env_refresh = os.environ.get("SLACK_REFRESH_TOKEN", "").strip()

    rotation_configured = bool(client_id and client_secret)

    with _lock:
        if _access_token and not _needs_refresh():
            return _access_token

        if not _access_token:
            stored = _load_persisted_tokens()
            if stored.get("access_token"):
                _access_token = stored["access_token"]
                _refresh_token = stored.get("refresh_token", env_refresh)
                _expires_at = stored.get("expires_at", 0.0)
                _last_refresh_at = stored.get("last_refresh_at", 0.0)
                if not _needs_refresh():
                    logger.info("Using persisted Slack access token (valid)")
                    return _access_token
                logger.info("Persisted Slack token expired, will refresh")

        current_refresh = _refresh_token or env_refresh
        if rotation_configured and current_refresh:
            try:
                result = _do_refresh(client_id, client_secret, current_refresh)
                new_access = result["access_token"]
                new_refresh = result.get("refresh_token", current_refresh)
                expires_in = result.get("expires_in", 43200)

                _access_token = new_access
                _refresh_token = new_refresh
                _expires_at = time.time() + expires_in
                _last_refresh_at = time.time()

                _set_token_env(new_access)
                if new_refresh != current_refresh:
                    os.environ["SLACK_REFRESH_TOKEN"] = new_refresh

                _persist_tokens(new_access, new_refresh, _expires_at)
                logger.info("Slack token refreshed (expires in %ds)", expires_in)
                return _access_token
            except RuntimeError as exc:
                err_msg = str(exc).lower()
                if "invalid_refresh_token" in err_msg:
                    logger.error(
                        "Refresh token is invalid/already used. "
                        "Re-run the initial token exchange or re-install the app."
                    )
                else:
                    logger.error("Slack token refresh failed: %s", exc)

        static = _get_token_env()
        if static:
            _access_token = static
            if _is_rotating_token(static):
                _expires_at = time.time() + 3600
            else:
                _expires_at = time.time() + 86400
            return _access_token

    return None


def invalidate() -> None:
    """Force re-fetch on next ``get_valid_token()`` call."""
    global _access_token, _refresh_token, _expires_at, _last_refresh_at
    with _lock:
        _access_token = None
        _refresh_token = None
        _expires_at = 0.0
        _last_refresh_at = 0.0
        logger.info("Slack token cache invalidated")


def token_status() -> dict:
    """Return diagnostic info about the current token state (no secrets)."""
    client_id = os.environ.get("SLACK_CLIENT_ID", "").strip()
    client_secret = os.environ.get("SLACK_CLIENT_SECRET", "").strip()
    env_refresh = os.environ.get("SLACK_REFRESH_TOKEN", "").strip()

    token_type = "none"
    if _access_token:
        if _is_rotating_token(_access_token):
            if _access_token.startswith("xoxe.xoxb-"):
                token_type = "rotating_bot"
            elif _access_token.startswith("xoxe.xoxp-"):
                token_type = "rotating_user"
            else:
                token_type = "rotating_unknown"
        elif _access_token.startswith("xoxb-"):
            token_type = "static_bot"
        elif _access_token.startswith("xoxp-"):
            token_type = "static_user"
        else:
            token_type = "unknown"

    return {
        "has_token": bool(_access_token),
        "token_type": token_type,
        "is_rotating": bool(_access_token and _is_rotating_token(_access_token)),
        "expires_at": _expires_at,
        "expires_in_seconds": max(0, int(_expires_at - time.time())),
        "last_refresh_at": _last_refresh_at,
        "rotation_configured": bool(client_id and client_secret),
        "has_refresh_token": bool(_refresh_token or env_refresh),
        "token_store": _token_store_path(),
    }
