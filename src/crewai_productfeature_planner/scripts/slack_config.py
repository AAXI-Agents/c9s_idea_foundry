"""Auto-configure Slack app request URLs after the public URL is resolved.

When the server starts, the public URL is determined by ``SERVER_ENV``:

* **DEV**  — ngrok tunnel URL (changes on restart unless ``NGROK_DOMAIN`` set)
* **UAT**  — ``DOMAIN_NAME_UAT`` (static)
* **PROD** — ``DOMAIN_NAME_PROD`` (static)

Slack must know the public URL for three surfaces:

1. **Interactivity & Shortcuts** → ``/slack/interactions``
2. **Event Subscriptions**       → ``/slack/events``
3. **OAuth Redirect URL**        → ``/slack/oauth/callback``

This module provides :func:`update_slack_app_urls` which:

* Uses the `Slack App Manifest API`_ to push the new URLs automatically
  when ``SLACK_APP_CONFIGURATION_TOKEN`` and ``SLACK_APP_ID`` are set.
* Falls back to printing actionable instructions when the tokens are not
  available.

.. _Slack App Manifest API:
   https://api.slack.com/reference/manifests

Environment variables
---------------------
``SLACK_APP_ID``
    The Slack app ID (visible in **Basic Information** on api.slack.com).
``SLACK_APP_CONFIGURATION_TOKEN``
    An *app-configuration token* (``xoxe.xoxp-…``) with
    ``app_management:write`` scope.  Generate one at
    https://api.slack.com/apps/<app-id>/app-level-tokens.

Both are optional.  When missing, the function logs a warning with the
manual steps to update the URLs in the Slack dashboard.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# Path to the manifest template shipped with the repo.
_MANIFEST_PATH = Path(__file__).resolve().parents[3] / "slack_manifest.json"

# Slack endpoint paths that must be registered.
_INTERACTIONS_PATH = "/slack/interactions"
_EVENTS_PATH = "/slack/events"
_OAUTH_CALLBACK_PATH = "/slack/oauth/callback"


# ── Public API ────────────────────────────────────────────────


def update_slack_app_urls(public_url: str) -> bool:
    """Update the Slack app's request URLs to point to *public_url*.

    Args:
        public_url: The public ``https://…`` URL from ngrok.

    Returns:
        ``True`` if the manifest was pushed to the Slack API;
        ``False`` if it fell back to manual instructions.
    """
    public_url = public_url.rstrip("/")

    interactions_url = f"{public_url}{_INTERACTIONS_PATH}"
    events_url = f"{public_url}{_EVENTS_PATH}"
    oauth_url = f"{public_url}{_OAUTH_CALLBACK_PATH}"

    app_id = os.environ.get("SLACK_APP_ID", "").strip()
    config_token = os.environ.get("SLACK_APP_CONFIGURATION_TOKEN", "").strip()

    if app_id and config_token:
        # Validate token type before calling the API.
        # The Manifest API requires an *app configuration token*
        # (prefix ``xoxe.xoxp-``).  App-level tokens (``xapp-``) and
        # regular bot tokens (``xoxb-``) will fail with
        # ``not_allowed_token_type``.
        if not config_token.startswith("xoxe."):
            _token_prefix = config_token.split("-")[0] if "-" in config_token else config_token[:4]
            logger.warning(
                "SLACK_APP_CONFIGURATION_TOKEN has prefix '%s' but "
                "the Manifest API requires an app-configuration token "
                "(prefix 'xoxe.xoxp-…'). Generate one at "
                "https://api.slack.com/apps/%s/general → "
                "App-Level Tokens (with scope 'configuration').  "
                "Current token type will be rejected by Slack.",
                _token_prefix, app_id or "<your-app-id>",
            )
            _print_manual_instructions(
                interactions_url, events_url, oauth_url, app_id,
            )
            return False

        return _update_via_api(
            app_id, config_token,
            interactions_url, events_url, oauth_url,
        )

    _print_manual_instructions(
        interactions_url, events_url, oauth_url, app_id,
    )
    return False


def build_manifest(
    interactions_url: str,
    events_url: str,
    oauth_url: str,
) -> dict[str, Any]:
    """Return a copy of the manifest template with URLs filled in.

    Reads the on-disk ``slack_manifest.json``, replaces the
    ``YOUR_NGROK_DOMAIN`` placeholder with the real URLs, and returns
    the resulting dict.
    """
    raw = _MANIFEST_PATH.read_text(encoding="utf-8")
    manifest: dict[str, Any] = json.loads(raw)

    # Settings → interactivity
    settings = manifest.setdefault("settings", {})
    interactivity = settings.setdefault("interactivity", {})
    interactivity["is_enabled"] = True
    interactivity["request_url"] = interactions_url

    # Settings → event subscriptions
    events = settings.setdefault("event_subscriptions", {})
    events["request_url"] = events_url

    # OAuth → redirect URLs
    oauth = manifest.setdefault("oauth_config", {})
    oauth["redirect_urls"] = [oauth_url]

    return manifest


# ── Internal helpers ──────────────────────────────────────────


def _update_via_api(
    app_id: str,
    config_token: str,
    interactions_url: str,
    events_url: str,
    oauth_url: str,
) -> bool:
    """Push the updated manifest to Slack via ``apps.manifest.update``."""
    try:
        import ssl as _ssl

        import certifi
        from slack_sdk import WebClient

        ssl_ctx = _ssl.create_default_context(cafile=certifi.where())
        client = WebClient(token=config_token, ssl=ssl_ctx)
    except ImportError:
        logger.error(
            "slack_sdk or certifi is not installed — "
            "cannot auto-update Slack app manifest"
        )
        _print_manual_instructions(
            interactions_url, events_url, oauth_url, app_id,
        )
        return False

    manifest = build_manifest(interactions_url, events_url, oauth_url)

    try:
        resp = client.api_call(
            "apps.manifest.update",
            json={"app_id": app_id, "manifest": manifest},
        )
        if resp.get("ok"):
            logger.info(
                "✅ Slack app manifest updated successfully "
                "(interactivity=%s, events=%s)",
                interactions_url, events_url,
            )
            return True
        else:
            error = resp.get("error", "unknown_error")
            errors = resp.get("errors", [])
            logger.warning(
                "Slack manifest update failed: %s %s",
                error, errors,
            )
            _print_manual_instructions(
                interactions_url, events_url, oauth_url, app_id,
            )
            return False
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Slack manifest API call failed: %s — "
            "falling back to manual instructions",
            exc,
        )
        _print_manual_instructions(
            interactions_url, events_url, oauth_url, app_id,
        )
        return False


def _print_manual_instructions(
    interactions_url: str,
    events_url: str,
    oauth_url: str,
    app_id: str = "",
) -> None:
    """Log clear instructions for manually updating Slack app URLs."""
    dashboard_url = (
        f"https://api.slack.com/apps/{app_id}" if app_id
        else "https://api.slack.com/apps"
    )

    logger.warning(
        "[SlackConfig] Ngrok URL changed — update Slack app URLs manually: "
        "Interactivity=%s  Events=%s  OAuth=%s  Dashboard=%s  "
        "(Tip: set SLACK_APP_ID + SLACK_APP_CONFIGURATION_TOKEN or NGROK_DOMAIN to automate)",
        interactions_url,
        events_url,
        oauth_url,
        dashboard_url,
    )
