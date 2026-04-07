"""SSO authentication dependency for the PRD Planner ("Idea Foundry") API.

Validates RS256 JWT access tokens issued by the C9 Single Sign-On
service.  Supports two validation modes (tried in order):

1. **Local RS256 decode** — If ``SSO_JWT_PUBLIC_KEY_PATH`` is set,
   tokens are verified locally with the RSA public key (fast, no
   network call).
2. **Remote introspection** — Calls ``SSO_BASE_URL/oauth/introspect``
   to verify the token against the SSO service (useful when the
   planner doesn't hold the public key).

When ``SSO_ENABLED`` is ``false`` (default for backward compatibility),
authentication is **bypassed** and all requests pass through.  This
preserves the existing open-access development workflow.

The authenticated ``app_id`` claim (if present) is verified against
the SSO-registered "Idea Foundry" application to ensure the token
was issued for *this* application.

Usage in routers::

    from crewai_productfeature_planner.apis.sso_auth import require_sso_user

    @router.get("/some-endpoint", dependencies=[Depends(require_sso_user)])
    async def protected_endpoint(): ...

    # Or to access the user claims:
    @router.get("/my-stuff")
    async def my_stuff(user: dict = Depends(require_sso_user)): ...
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
from fastapi import HTTPException, Request, status

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# ── Application identity ──────────────────────────────────────

APP_NAME = "Idea Foundry"

_RS256_ALGORITHM = "RS256"

# ── Configuration helpers ─────────────────────────────────────


def _sso_enabled() -> bool:
    """Return True if SSO auth enforcement is turned on."""
    return os.environ.get("SSO_ENABLED", "false").strip().lower() in (
        "true", "1", "yes",
    )


def _sso_base_url() -> str:
    return os.environ.get("SSO_BASE_URL", "http://localhost:8100").strip().rstrip("/")


def _sso_issuer() -> str:
    return os.environ.get("SSO_ISSUER", "c9s-sso").strip()


def _sso_webhook_secret() -> str:
    return os.environ.get("SSO_WEBHOOK_SECRET", "").strip()


@lru_cache(maxsize=1)
def _sso_public_key() -> str | None:
    """Load the RS256 public key from disk (cached after first read)."""
    key_path = os.environ.get("SSO_JWT_PUBLIC_KEY_PATH", "").strip()
    if not key_path:
        return None
    try:
        return Path(key_path).read_text()
    except Exception:
        logger.warning("[SSO Auth] Could not read public key from %s", key_path, exc_info=True)
        return None


# ── Local RS256 JWT decode ────────────────────────────────────


def _decode_jwt_locally(token: str) -> dict[str, Any] | None:
    """Decode and verify a JWT using the SSO RS256 public key.

    Returns claims dict on success, None on failure.
    """
    public_key = _sso_public_key()
    if not public_key:
        return None

    try:
        from jose import jwt as jose_jwt

        claims = jose_jwt.decode(
            token,
            public_key,
            algorithms=[_RS256_ALGORITHM],
            issuer=_sso_issuer(),
            options={"require_sub": True, "require_exp": True},
        )
        # Ensure this is an access token, not a refresh token.
        if claims.get("type") != "access":
            logger.debug("[SSO Auth] Token type is '%s', expected 'access'", claims.get("type"))
            return None
        return claims
    except Exception:
        logger.debug("[SSO Auth] Local RS256 JWT decode failed", exc_info=True)
        return None


# ── Remote introspection ──────────────────────────────────────


def _introspect_remotely(token: str) -> dict[str, Any] | None:
    """Call the SSO service's ``/sso/oauth/introspect`` endpoint.

    Returns the introspection dict on success (``active: True``),
    None on failure.
    """
    base_url = _sso_base_url()
    try:
        resp = httpx.post(
            f"{base_url}/sso/oauth/introspect",
            json={"token": token},
            timeout=5.0,
        )
        if resp.status_code == 200:
            body = resp.json()
            if body.get("active"):
                return body
        logger.debug(
            "[SSO Auth] Remote introspection returned %d", resp.status_code,
        )
    except Exception:
        logger.warning("[SSO Auth] Remote introspection failed", exc_info=True)
    return None


# ── App-ID validation ─────────────────────────────────────────


def _validate_app_id(claims: dict[str, Any]) -> None:
    """Verify the token was issued for the Idea Foundry application.

    Tokens issued through the OAuth authorization-code flow carry an
    ``app_id`` claim.  Tokens from direct ``/auth/login`` (no OAuth
    client) have an empty ``app_id``.

    When ``SSO_EXPECTED_APP_ID`` is configured, tokens MUST carry a
    matching ``app_id``.  Otherwise, direct-login tokens are accepted
    alongside any registered client tokens.
    """
    expected = os.environ.get("SSO_EXPECTED_APP_ID", "").strip()
    if not expected:
        # No specific app enforcement — accept any valid SSO token.
        return

    token_app_id = claims.get("app_id", "")
    if token_app_id != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Token not issued for {APP_NAME}. "
                f"Expected app_id '{expected}', got '{token_app_id}'."
            ),
        )


# ── FastAPI dependency ────────────────────────────────────────


async def require_sso_user(request: Request) -> dict[str, Any]:
    """FastAPI dependency that enforces SSO authentication.

    When SSO is enabled, extracts the Bearer token from the
    ``Authorization`` header, validates it (locally via RS256 public
    key or remotely via introspection), verifies the ``app_id`` claim,
    and returns a normalised user-claims dict.

    When SSO is disabled (``SSO_ENABLED=false``), returns a
    placeholder user so existing dev workflows are unaffected.
    """
    if not _sso_enabled():
        logger.debug("[SSO] Auth bypassed — SSO disabled")
        return {
            "user_id": "anonymous",
            "email": "dev@localhost",
            "roles": ["admin"],
            "app_name": APP_NAME,
            "display_name": "Developer (SSO disabled)",
        }

    # Extract Bearer token from Authorization header.
    auth: str = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        logger.warning("[SSO] Missing Bearer token from %s", request.url.path)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Missing Bearer token — authenticate via the C9 SSO service for {APP_NAME}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = auth[len("Bearer "):]

    # Try local RS256 decode first, then remote introspection.
    claims = _decode_jwt_locally(token) or _introspect_remotely(token)

    if not claims:
        logger.warning("[SSO] Invalid/expired token for %s", request.url.path)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify the token was issued for this application.
    _validate_app_id(claims)

    user_id = claims.get("sub", "")
    logger.info("[SSO] Authenticated user_id=%s path=%s", user_id, request.url.path)
    return {
        "user_id": user_id,
        "email": claims.get("email", ""),
        "roles": claims.get("roles", []),
        "app_id": claims.get("app_id", ""),
        "app_name": APP_NAME,
        "enterprise_id": claims.get("enterprise_id", ""),
        "organization_id": claims.get("organization_id", ""),
        "display_name": claims.get("display_name", claims.get("email", "")),
    }


# ── Webhook signature verification ───────────────────────────


async def verify_sso_webhook(request: Request) -> dict[str, Any]:
    """FastAPI dependency that verifies inbound SSO webhook payloads.

    The SSO webhook service signs payloads with HMAC-SHA256 and sends
    the hex digest in the ``X-Webhook-Signature`` header.
    """
    secret = _sso_webhook_secret()
    if not secret:
        # No secret configured — pass through (dev mode).
        return await request.json()

    signature = request.headers.get("X-Webhook-Signature", "")
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Webhook-Signature header",
        )

    body = await request.body()
    computed = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(computed, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    return json.loads(body)
