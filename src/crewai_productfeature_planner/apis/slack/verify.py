"""
Slack request verification.

Implements Slack's request signing protocol to authenticate inbound
HTTP requests from Slack (slash commands, events, interactive payloads).

Protocol (https://docs.slack.dev/authentication/verifying-requests-from-slack):

1. Extract ``X-Slack-Request-Timestamp`` and ``X-Slack-Signature`` headers.
2. Reject requests older than 5 minutes (replay-attack protection).
3. Build the signature base string:  ``v0:<timestamp>:<raw_body>``
4. Compute ``v0=<HMAC-SHA256(signing_secret, base_string)>``
5. Compare with ``X-Slack-Signature`` using constant-time comparison.

Fall-back: If only the deprecated ``SLACK_VERIFICATION_TOKEN`` is set,
verify using the ``token`` field in the request body instead.

Env vars:
    SLACK_SIGNING_SECRET      – Preferred (HMAC-SHA256 signing secret)
    SLACK_VERIFICATION_TOKEN  – Deprecated fallback (plain-text token comparison)
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time

from fastapi import HTTPException, Request

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

_SIGNING_SECRET_KEY = "SLACK_SIGNING_SECRET"
_VERIFICATION_TOKEN_KEY = "SLACK_VERIFICATION_TOKEN"
_MAX_TIMESTAMP_AGE_SECONDS = 300


def _get_signing_secret() -> str:
    return os.environ.get(_SIGNING_SECRET_KEY, "").strip()


def _get_verification_token() -> str:
    return os.environ.get(_VERIFICATION_TOKEN_KEY, "").strip()


def _compute_signature(signing_secret: str, timestamp: str, body: bytes) -> str:
    """Compute ``v0=<hex-digest>`` per Slack's signing spec."""
    base_string = f"v0:{timestamp}:".encode() + body
    digest = hmac.new(
        signing_secret.encode(),
        base_string,
        hashlib.sha256,
    ).hexdigest()
    return f"v0={digest}"


async def verify_slack_request(request: Request) -> None:
    """FastAPI dependency that verifies inbound Slack requests.

    Checks the ``X-Slack-Signature`` header using the signing secret.
    If no signing secret is configured, falls back to the deprecated
    verification-token check.  If neither is configured the request
    passes through (allows testing without Slack credentials).
    """
    signing_secret = _get_signing_secret()
    verification_token = _get_verification_token()

    if not signing_secret and not verification_token:
        return

    # ---- Preferred: HMAC-SHA256 signing secret ----
    if signing_secret:
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
        slack_signature = request.headers.get("X-Slack-Signature", "")

        if not timestamp or not slack_signature:
            logger.warning("Slack request missing signature headers")
            raise HTTPException(status_code=401, detail="Missing Slack signature headers")

        try:
            ts = int(timestamp)
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid X-Slack-Request-Timestamp")

        if abs(time.time() - ts) > _MAX_TIMESTAMP_AGE_SECONDS:
            logger.warning("Slack request timestamp too old: %s", timestamp)
            raise HTTPException(status_code=401, detail="Slack request timestamp is too old")

        body = await request.body()
        expected = _compute_signature(signing_secret, timestamp, body)

        if not hmac.compare_digest(expected, slack_signature):
            logger.warning("Slack request signature mismatch")
            raise HTTPException(status_code=401, detail="Invalid Slack request signature")
        return

    # ---- Fallback: deprecated verification token ----
    if verification_token:
        body = await request.body()
        try:
            import json as _json
            payload = _json.loads(body)
        except Exception:
            from urllib.parse import parse_qs
            payload = {
                k: v[0] if len(v) == 1 else v
                for k, v in parse_qs(body.decode("utf-8", errors="replace")).items()
            }
        req_token = payload.get("token", "")
        if not hmac.compare_digest(str(req_token), verification_token):
            logger.warning("Slack verification token mismatch")
            raise HTTPException(status_code=401, detail="Invalid Slack verification token")
