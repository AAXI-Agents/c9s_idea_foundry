"""Background Slack token refresh scheduler.

Proactively refreshes Slack rotating tokens **before** they expire so
the bot never ends up with a dead token that requires manual
re-installation.

Slack's configurable token rotation gives you a 12-hour access token
and a **single-use** refresh token.  If the server is down during the
refresh window and the access token expires, the refresh token becomes
invalid too (``invalid_refresh_token``), permanently bricking the token
pair until the user re-installs the app.

This scheduler prevents that by refreshing tokens in the background
well before they expire, regardless of whether any Slack API calls are
happening.

Environment variables:

* ``TOKEN_REFRESH_INTERVAL_SECONDS`` — how often to check (default:
  ``1800`` = 30 minutes).
* ``TOKEN_REFRESH_BUFFER_SECONDS`` — refresh when the token's
  remaining lifetime drops below this value (default: ``3600`` =
  1 hour).
* ``TOKEN_REFRESH_SCHEDULER_ENABLED`` — set to ``"0"`` or ``"false"``
  to disable (default: enabled when ``SLACK_CLIENT_ID`` +
  ``SLACK_CLIENT_SECRET`` are set).
"""

from __future__ import annotations

import os
import threading
import time

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# ── Module-level state ────────────────────────────────────────────────

_scheduler_thread: threading.Thread | None = None
_stop_event = threading.Event()

_DEFAULT_INTERVAL_SECONDS = 1800  # 30 minutes
_DEFAULT_BUFFER_SECONDS = 3600  # 1 hour — refresh when < 1 h remaining


# ── Public helpers ────────────────────────────────────────────────────


def get_scheduler_status() -> dict:
    """Return a dict describing the current scheduler state."""
    return {
        "running": _scheduler_thread is not None and _scheduler_thread.is_alive(),
        "interval_seconds": _get_interval_seconds(),
        "buffer_seconds": _get_buffer_seconds(),
    }


# ── Start / stop ─────────────────────────────────────────────────────


def start_token_refresh_scheduler() -> bool:
    """Start the background token refresh scheduler.

    Returns ``True`` if the scheduler was started, ``False`` if already
    running, disabled, or no rotation credentials are available.
    """
    global _scheduler_thread  # noqa: PLW0603

    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        logger.debug("[TokenRefresh] Already running")
        return False

    # Check env-var override
    enabled_env = os.environ.get(
        "TOKEN_REFRESH_SCHEDULER_ENABLED", ""
    ).strip().lower()
    if enabled_env in ("0", "false", "no"):
        logger.info("[TokenRefresh] Disabled via TOKEN_REFRESH_SCHEDULER_ENABLED")
        return False

    # Need client credentials to perform token rotation
    client_id = os.environ.get("SLACK_CLIENT_ID", "").strip()
    client_secret = os.environ.get("SLACK_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        logger.info(
            "[TokenRefresh] No SLACK_CLIENT_ID / SLACK_CLIENT_SECRET — "
            "scheduler not started"
        )
        return False

    _stop_event.clear()
    _scheduler_thread = threading.Thread(
        target=_scheduler_loop,
        name="token-refresh-scheduler",
        daemon=True,
    )
    _scheduler_thread.start()

    interval = _get_interval_seconds()
    buffer = _get_buffer_seconds()
    logger.info(
        "[TokenRefresh] Started — checking every %ds, refreshing when "
        "< %ds remaining",
        interval,
        buffer,
    )
    return True


def stop_token_refresh_scheduler() -> None:
    """Signal the scheduler thread to stop."""
    global _scheduler_thread  # noqa: PLW0603
    _stop_event.set()
    if _scheduler_thread is not None:
        _scheduler_thread.join(timeout=15)
        _scheduler_thread = None
    logger.info("[TokenRefresh] Stopped")


# ── Internal ──────────────────────────────────────────────────────────


def _get_interval_seconds() -> int:
    try:
        return int(os.environ.get("TOKEN_REFRESH_INTERVAL_SECONDS", ""))
    except (ValueError, TypeError):
        return _DEFAULT_INTERVAL_SECONDS


def _get_buffer_seconds() -> int:
    try:
        return int(os.environ.get("TOKEN_REFRESH_BUFFER_SECONDS", ""))
    except (ValueError, TypeError):
        return _DEFAULT_BUFFER_SECONDS


def _scheduler_loop() -> None:
    """Main loop — runs in a daemon thread."""
    interval = _get_interval_seconds()
    logger.debug("[TokenRefresh] Loop started (interval=%ds)", interval)

    # Run the first refresh check immediately on startup so tokens
    # that expired while the server was down get refreshed right away.
    try:
        _refresh_expiring_tokens()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[TokenRefresh] Initial refresh failed: %s", exc)

    while not _stop_event.is_set():
        _stop_event.wait(timeout=interval)
        if _stop_event.is_set():
            break
        try:
            _refresh_expiring_tokens()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[TokenRefresh] Refresh sweep error: %s", exc)


def _refresh_expiring_tokens() -> int:
    """Check all teams and refresh tokens that are close to expiring.

    Returns the number of tokens successfully refreshed.
    """
    from crewai_productfeature_planner.mongodb.slack_oauth.repository import (
        get_all_teams,
    )
    from crewai_productfeature_planner.tools.slack_token_manager import (
        _is_rotating_token,
        get_valid_token,
    )

    teams = get_all_teams()
    if not teams:
        return 0

    buffer = _get_buffer_seconds()
    now = time.time()
    refreshed = 0

    for team in teams:
        team_id = team.get("team_id", "")
        access_token = team.get("access_token", "")
        refresh_token = team.get("refresh_token")
        expires_at = team.get("expires_at", 0.0)

        if not team_id or not access_token:
            continue

        # Skip static (non-rotating) tokens — they don't expire
        if not _is_rotating_token(access_token) and not refresh_token:
            continue

        remaining = expires_at - now
        if remaining > buffer:
            logger.debug(
                "[TokenRefresh] team=%s OK — %d seconds remaining",
                team_id,
                int(remaining),
            )
            continue

        # Token is expiring soon or already expired — trigger refresh
        logger.info(
            "[TokenRefresh] team=%s needs refresh — %s remaining",
            team_id,
            f"{int(remaining)}s" if remaining > 0 else "EXPIRED",
        )

        token = get_valid_token(team_id)
        if token:
            refreshed += 1
            logger.info(
                "[TokenRefresh] team=%s refreshed successfully", team_id
            )
        else:
            logger.error(
                "[TokenRefresh] team=%s refresh FAILED — token is "
                "permanently invalid. The Slack app must be "
                "re-installed via OAuth.",
                team_id,
            )

    if refreshed:
        logger.info("[TokenRefresh] Sweep complete — %d token(s) refreshed", refreshed)

    return refreshed
