"""SSO authentication router — proxies auth requests to the C9 SSO service.

All endpoints are public (no Bearer required) except where noted.
The router prefix is ``/auth/sso`` and all endpoints are tagged ``SSO``.
"""

from __future__ import annotations

import html as _html
import os
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from crewai_productfeature_planner.apis.sso_auth import (
    _decode_jwt_locally,
    _fetch_and_save_public_key,
    _introspect_remotely,
    _sso_base_url,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth/sso", tags=["SSO"])

# ── Module-level state ────────────────────────────────────────

_pending_sso_auth: dict[str, Any] = {}

# Shared headers for SSO proxy requests.  ngrok-skip-browser-warning
# prevents ngrok from returning an HTML interstitial page.
_SSO_PROXY_HEADERS: dict[str, str] = {
    "Content-Type": "application/json",
    "ngrok-skip-browser-warning": "true",
}


def _sso_proxy_headers(*, auth: str | None = None) -> dict[str, str]:
    """Build headers for an SSO proxy request.

    Always includes Content-Type and ngrok-skip-browser-warning.
    If *auth* is provided, it is forwarded so the SSO server can
    validate Bearer tokens for protected endpoints.
    """
    headers = {**_SSO_PROXY_HEADERS}
    if auth:
        headers["Authorization"] = auth
    return headers


async def _sso_proxy_post(
    path: str,
    *,
    json: dict | None = None,
    auth: str | None = None,
    label: str = "SSO proxy",
) -> JSONResponse:
    """Async proxy POST to the SSO server.

    Returns a ``JSONResponse`` mirroring the upstream status code and body.
    On connection failure returns 502; on timeout returns 504.
    """
    sso_base = _sso_base_url()
    url = f"{sso_base}{path}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                json=json,
                headers=_sso_proxy_headers(auth=auth),
            )
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except httpx.ConnectError as exc:
        logger.error("[SSO] %s connect failed: %s", label, exc, exc_info=True)
        return JSONResponse(
            {"error": f"SSO server unreachable: {exc}"},
            status_code=502,
        )
    except httpx.TimeoutException as exc:
        logger.error("[SSO] %s timed out: %s", label, exc, exc_info=True)
        return JSONResponse(
            {"error": f"SSO server timed out: {exc}"},
            status_code=504,
        )
    except Exception as exc:
        logger.error("[SSO] %s failed: %s", label, exc, exc_info=True)
        return JSONResponse(
            {"error": f"SSO server unreachable: {exc}"},
            status_code=502,
        )


def _get_public_url() -> str:
    """Resolve this server's public URL for OAuth callbacks.

    Uses ``get_public_url`` from ngrok_tunnel when available,
    otherwise falls back to ``http://localhost:{port}``.
    """
    from crewai_productfeature_planner.scripts.ngrok_tunnel import (
        get_server_env,
    )

    env = get_server_env()

    if env == "UAT":
        domain = os.environ.get("DOMAIN_NAME_UAT", "").strip()
        if domain:
            if not domain.startswith("http"):
                domain = f"https://{domain}"
            return domain.rstrip("/")

    if env == "PROD":
        domain = os.environ.get("DOMAIN_NAME_PROD", "").strip()
        if domain:
            if not domain.startswith("http"):
                domain = f"https://{domain}"
            return domain.rstrip("/")

    # DEV: prefer NGROK_DOMAIN if set (avoids starting a tunnel)
    ngrok_domain = os.environ.get("NGROK_DOMAIN", "").strip()
    if ngrok_domain:
        if not ngrok_domain.startswith("http"):
            return f"https://{ngrok_domain}"
        return ngrok_domain.rstrip("/")

    port = int(os.environ.get("PORT", "8000"))
    return f"http://localhost:{port}"


# ── OAuth2 redirect login ────────────────────────────────────


@router.get(
    "/login",
    summary="Start SSO sign-in (OAuth2 redirect)",
    response_class=RedirectResponse,
    status_code=307,
)
async def sso_login(
    request: Request,
    redirect_after: str = Query(
        "/",
        description="URL to redirect to after successful sign-in",
    ),
):
    """Redirect the user to the SSO authorization endpoint.

    After the user authenticates, they are redirected back to
    ``/auth/sso/callback`` with an authorization code which is
    exchanged for access + refresh tokens.
    """
    sso_base = _sso_base_url()
    client_id = os.environ.get("SSO_CLIENT_ID", "").strip()
    if not client_id:
        return JSONResponse(
            {"error": "SSO_CLIENT_ID not configured"},
            status_code=503,
        )

    callback_url = f"{_get_public_url()}/auth/sso/callback"

    state = secrets.token_urlsafe(32)
    _pending_sso_auth["sso_state"] = state
    _pending_sso_auth["sso_redirect_after"] = redirect_after

    params = urlencode({
        "client_id": client_id,
        "redirect_uri": callback_url,
        "response_type": "code",
        "scope": "openid profile email",
        "state": state,
    })

    authorize_url = f"{sso_base}/oauth/authorize?{params}"
    return RedirectResponse(authorize_url)


# ── OAuth2 callback ──────────────────────────────────────────


@router.get(
    "/callback",
    summary="SSO OAuth2 callback",
    response_class=HTMLResponse,
)
async def sso_callback(
    request: Request,
    code: str = Query("", description="Authorization code from SSO"),
    state: str = Query("", description="CSRF state parameter"),
    error: str = Query("", description="Error code if sign-in failed"),
    error_description: str = Query("", description="Error details"),
):
    """Handle the SSO redirect after user authentication.

    Exchanges the authorization code for access and refresh tokens.
    """
    if error:
        safe_err = _html.escape(error_description or error)
        return HTMLResponse(
            f"<h2>SSO Sign-In Failed</h2><p>{safe_err}</p>",
            status_code=400,
        )

    # Validate CSRF state
    expected_state = _pending_sso_auth.get("sso_state", "")
    if not state or state != expected_state:
        return HTMLResponse(
            "<h2>Invalid State</h2><p>CSRF state mismatch.</p>",
            status_code=400,
        )

    sso_base = _sso_base_url()
    callback_url = f"{_get_public_url()}/auth/sso/callback"

    # Exchange code for tokens
    try:
        async with httpx.AsyncClient(timeout=10.0) as ac:
            resp = await ac.post(
                f"{sso_base}/oauth/token",
                json={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": os.environ.get("SSO_CLIENT_ID", ""),
                    "client_secret": os.environ.get("SSO_CLIENT_SECRET", ""),
                    "redirect_uri": callback_url,
                },
            )
        resp.raise_for_status()
        tokens = resp.json()
    except Exception as exc:
        logger.error("[SSO] Token exchange failed: %s", exc, exc_info=True)
        return HTMLResponse(
            f"<h2>Token Exchange Failed</h2><p>Please try again.</p>",
            status_code=502,
        )

    _pending_sso_auth["sso_tokens"] = tokens
    logger.info("[SSO] OAuth authentication successful")

    redirect_after = _pending_sso_auth.pop("sso_redirect_after", "/")
    _pending_sso_auth.pop("sso_state", None)

    # Validate redirect_after to prevent open-redirect / XSS
    if not redirect_after.startswith("/"):
        base = _get_public_url()
        if not redirect_after.startswith(base):
            logger.warning(
                "[SSO] Blocked redirect to external URL: %s", redirect_after,
            )
            redirect_after = "/"

    if redirect_after.startswith("/"):
        redirect_after = f"{_get_public_url()}{redirect_after}"

    safe_url = _html.escape(redirect_after, quote=True)

    return HTMLResponse(
        f"<h2>SSO Sign-In Successful</h2>"
        f"<p>Redirecting...</p>"
        f'<script>setTimeout(function(){{window.location="{safe_url}"}}, 1500)</script>'
    )


# ── Direct login (email + password → tokens or 2FA) ─────────


@router.post(
    "/login",
    summary="SSO login — credentials → tokens or 2FA challenge",
    responses={
        200: {
            "description": (
                "**Dual response** depending on user's 2FA setting:\n\n"
                "- **2FA disabled** → tokens with `access_token`, "
                "`refresh_token`, `expires_in`\n"
                "- **2FA enabled** → `two_factor_required`, `login_token`, "
                "`email`, `expires_in` — follow up with "
                "`POST /auth/sso/login/verify-2fa`"
            ),
        },
        400: {"description": "Missing email or password"},
        401: {"description": "Invalid credentials"},
        502: {"description": "SSO server unreachable"},
    },
)
async def sso_direct_login(request: Request):
    """Proxy login to the SSO server.

    Expects JSON body: ``{"email": "...", "password": "..."}``

    The SSO server returns tokens directly (when 2FA is disabled)
    or a ``login_token`` for the 2FA challenge.
    """
    client_id = os.environ.get("SSO_CLIENT_ID", "").strip()

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    if not body.get("email") or not body.get("password"):
        return JSONResponse(
            {"error": "email and password are required"},
            status_code=400,
        )

    payload = {**body, "client_id": client_id}

    return await _sso_proxy_post(
        "/sso/auth/login",
        json=payload,
        label="Direct login",
    )


# ── Login 2FA verification ───────────────────────────────────


@router.post(
    "/login/verify-2fa",
    summary="SSO login — verify 2FA code → tokens",
    responses={
        200: {"description": "Login successful — JWT tokens returned"},
        400: {"description": "Missing email, login_token, or code"},
        401: {"description": "Invalid or expired 2FA code"},
        502: {"description": "SSO server unreachable"},
    },
)
async def sso_login_verify_2fa(request: Request):
    """Complete login by verifying the 2FA code.

    Expects JSON body: ``{"email": "...", "login_token": "...", "code": "123456"}``
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    if not body.get("email") or not body.get("login_token") or not body.get("code"):
        return JSONResponse(
            {"error": "email, login_token, and code are required"},
            status_code=400,
        )

    return await _sso_proxy_post(
        "/sso/auth/login/verify-2fa",
        json=body,
        label="Login verify-2fa",
    )


# ── Google Sign-In ────────────────────────────────────────────


@router.post(
    "/google",
    summary="Google Sign-In (ID token → JWT tokens)",
    responses={
        200: {"description": "Login successful — JWT tokens returned"},
        400: {"description": "Missing id_token"},
        401: {"description": "Invalid Google ID token"},
        502: {"description": "SSO server unreachable"},
    },
)
async def sso_google_login(request: Request):
    """Proxy Google Sign-In to the SSO server.

    Expects JSON body: ``{"id_token": "eyJhbGci..."}``
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    if not body.get("id_token"):
        return JSONResponse(
            {"error": "id_token is required"},
            status_code=400,
        )

    return await _sso_proxy_post(
        "/sso/auth/google",
        json=body,
        label="Google login",
    )


# ── Registration ──────────────────────────────────────────────


@router.get(
    "/register",
    summary="Redirect to SSO registration",
    response_class=RedirectResponse,
    status_code=307,
)
async def sso_register_redirect(
    request: Request,
    redirect_after: str = Query(
        "/",
        description="URL to redirect to after registration and login",
    ),
):
    """Redirect the user to the SSO registration page."""
    sso_base = _sso_base_url()
    login_url = f"{_get_public_url()}/auth/sso/login?redirect_after={redirect_after}"
    params = urlencode({"redirect_uri": login_url})
    return RedirectResponse(f"{sso_base}/users/register?{params}")


@router.post(
    "/register",
    summary="SSO register — create account → 2FA challenge",
    status_code=201,
    responses={
        201: {"description": "Account created — 2FA code sent to email"},
        400: {"description": "Missing email or password"},
        409: {"description": "User already exists"},
        502: {"description": "SSO server unreachable"},
    },
)
async def sso_register_user(request: Request):
    """Proxy user registration to the SSO server.

    Expects JSON body: ``{"email": "...", "password": "..."}``
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    if not body.get("email") or not body.get("password"):
        return JSONResponse(
            {"error": "email and password are required"},
            status_code=400,
        )

    # Inject app_id so the user is associated with Idea Foundry
    if not body.get("app_id"):
        app_id = os.environ.get("SSO_CLIENT_ID", "").strip()
        if app_id:
            body["app_id"] = app_id

    return await _sso_proxy_post(
        "/sso/users/register",
        json=body,
        label="Register",
    )


@router.post(
    "/register/verify-2fa",
    summary="SSO register — verify email 2FA code",
    responses={
        200: {"description": "Account activated"},
        400: {"description": "Missing email or code"},
        502: {"description": "SSO server unreachable"},
    },
)
async def sso_register_verify_2fa(request: Request):
    """Verify the registration 2FA code to activate the account.

    Expects JSON body: ``{"email": "...", "code": "123456"}``
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    if not body.get("email") or not body.get("code"):
        return JSONResponse(
            {"error": "email and code are required"},
            status_code=400,
        )

    return await _sso_proxy_post(
        "/sso/users/register/verify-2fa",
        json=body,
        label="Register verify-2fa",
    )


@router.post(
    "/register/resend-2fa",
    summary="Resend registration 2FA code",
    responses={
        200: {"description": "2FA code resent to email"},
        400: {"description": "Missing email"},
        502: {"description": "SSO server unreachable"},
    },
)
async def sso_register_resend_2fa(request: Request):
    """Resend the registration 2FA code.

    Expects JSON body: ``{"email": "..."}``
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    if not body.get("email"):
        return JSONResponse({"error": "email is required"}, status_code=400)

    return await _sso_proxy_post(
        "/sso/users/register/resend-2fa",
        json=body,
        label="Register resend-2fa",
    )


# ── SSO status / userinfo ────────────────────────────────────


@router.get(
    "/status",
    summary="SSO authentication status",
)
async def sso_status(request: Request):
    """Check whether the current request has a valid SSO token.

    If a Bearer token is present it is validated; otherwise falls
    back to session tokens from the OAuth callback flow.
    """
    # Check Bearer token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer "):]
        # Remote-first: introspection is authoritative
        claims = await _introspect_remotely(token)
        if claims is None:
            claims = _decode_jwt_locally(token)
        if claims is None:
            new_key = await _fetch_and_save_public_key()
            if new_key:
                claims = _decode_jwt_locally(token)
        if claims:
            return {
                "authenticated": True,
                "user_id": claims.get("sub", ""),
                "email": claims.get("email", ""),
                "roles": claims.get("roles", []),
            }
        return {"authenticated": False, "reason": "token_expired_or_invalid"}

    # Fallback: check session tokens from OAuth callback
    tokens = _pending_sso_auth.get("sso_tokens")
    if not tokens:
        return {
            "authenticated": False,
            "sso_configured": bool(os.environ.get("SSO_CLIENT_ID")),
        }

    access_token = tokens.get("access_token", "")
    claims = await _introspect_remotely(access_token)
    if claims is None:
        claims = _decode_jwt_locally(access_token)
    if claims is None:
        new_key = await _fetch_and_save_public_key()
        if new_key:
            claims = _decode_jwt_locally(access_token)
    if claims:
        return {
            "authenticated": True,
            "user_id": claims.get("sub", ""),
            "email": claims.get("email", ""),
            "roles": claims.get("roles", []),
        }
    return {"authenticated": False, "reason": "token_expired_or_invalid"}


@router.get(
    "/userinfo",
    summary="Get current SSO user profile",
)
async def sso_userinfo(request: Request):
    """Return the SSO user profile from the Bearer token.

    Requires ``Authorization: Bearer <sso_access_token>`` header.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            {"error": "Missing Bearer token"},
            status_code=401,
        )

    token = auth_header[len("Bearer "):]
    # Remote-first: introspection is authoritative
    claims = await _introspect_remotely(token)
    if claims is None:
        claims = _decode_jwt_locally(token)
    if claims is None:
        new_key = await _fetch_and_save_public_key()
        if new_key:
            claims = _decode_jwt_locally(token)
    if not claims:
        return JSONResponse(
            {"error": "Invalid or expired access token"},
            status_code=401,
        )

    return {
        "user_id": claims.get("sub", ""),
        "email": claims.get("email", ""),
        "roles": claims.get("roles", []),
        "enterprise_id": claims.get("enterprise_id", ""),
        "organization_id": claims.get("organization_id", ""),
    }


# ── Password reset ───────────────────────────────────────────


@router.post(
    "/password-reset",
    summary="Request a password reset email",
    responses={
        200: {"description": "Password reset code sent to email"},
        400: {"description": "Missing email"},
        502: {"description": "SSO server unreachable"},
    },
)
async def sso_password_reset_request(request: Request):
    """Proxy a password-reset request to the SSO server.

    Expects JSON body: ``{"email": "..."}``
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    if not body.get("email"):
        return JSONResponse({"error": "email is required"}, status_code=400)

    return await _sso_proxy_post(
        "/sso/users/password-reset",
        json=body,
        label="Password-reset",
    )


@router.post(
    "/password-reset/confirm",
    summary="Confirm password reset with 2FA code",
    responses={
        200: {"description": "Password updated successfully"},
        400: {"description": "Missing fields"},
        502: {"description": "SSO server unreachable"},
    },
)
async def sso_password_reset_confirm(request: Request):
    """Proxy a password-reset confirmation to the SSO server.

    Expects JSON body: ``{"email": "...", "code": "123456", "new_password": "..."}``
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    if not body.get("email") or not body.get("code") or not body.get("new_password"):
        return JSONResponse(
            {"error": "email, code, and new_password are required"},
            status_code=400,
        )

    return await _sso_proxy_post(
        "/sso/users/password-reset/confirm",
        json=body,
        label="Password-reset confirm",
    )


# ── Token refresh ────────────────────────────────────────────


@router.post(
    "/token/refresh",
    summary="Refresh SSO access token",
    responses={
        200: {"description": "New token pair returned"},
        400: {"description": "Missing refresh_token"},
        401: {"description": "Invalid or expired refresh token"},
        502: {"description": "SSO server unreachable"},
    },
)
async def sso_token_refresh(request: Request):
    """Proxy a token-refresh request to the SSO server.

    Expects JSON body: ``{"refresh_token": "..."}``
    """
    client_id = os.environ.get("SSO_CLIENT_ID", "").strip()

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    if not body.get("refresh_token"):
        return JSONResponse(
            {"error": "refresh_token is required"},
            status_code=400,
        )

    payload = {**body, "client_id": client_id}

    return await _sso_proxy_post(
        "/sso/auth/refresh",
        json=payload,
        label="Token refresh",
    )


# ── Re-authentication ────────────────────────────────────────


@router.post(
    "/reauth",
    summary="Re-authenticate (Bearer + password → 2FA challenge)",
    responses={
        200: {"description": "2FA challenge issued"},
        400: {"description": "Missing password"},
        401: {"description": "Invalid credentials or missing Bearer"},
        502: {"description": "SSO server unreachable"},
    },
)
async def sso_reauth(request: Request):
    """Re-authenticate the current user for sensitive operations.

    Requires Bearer token AND password.
    Expects JSON body: ``{"password": "..."}``
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    if not body.get("password"):
        return JSONResponse(
            {"error": "password is required"},
            status_code=400,
        )

    auth_header = request.headers.get("authorization")

    return await _sso_proxy_post(
        "/sso/auth/reauth",
        json=body,
        auth=auth_header,
        label="Reauth",
    )


@router.post(
    "/reauth/verify-2fa",
    summary="Re-authenticate — verify 2FA code",
    responses={
        200: {"description": "Re-authentication confirmed"},
        400: {"description": "Missing reauth_token or code"},
        401: {"description": "Invalid code or missing Bearer"},
        502: {"description": "SSO server unreachable"},
    },
)
async def sso_reauth_verify_2fa(request: Request):
    """Verify re-authentication 2FA code.

    Requires Bearer token.
    Expects JSON body: ``{"reauth_token": "...", "code": "123456"}``
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    if not body.get("reauth_token") or not body.get("code"):
        return JSONResponse(
            {"error": "reauth_token and code are required"},
            status_code=400,
        )

    auth_header = request.headers.get("authorization")

    return await _sso_proxy_post(
        "/sso/auth/reauth/verify-2fa",
        json=body,
        auth=auth_header,
        label="Reauth verify-2fa",
    )


# ── Logout ────────────────────────────────────────────────────


@router.post(
    "/logout",
    summary="Logout (revoke current token)",
    responses={
        200: {"description": "Token revoked — user logged out"},
        401: {"description": "Missing or invalid Bearer token"},
        502: {"description": "SSO server unreachable"},
    },
)
async def sso_logout(request: Request):
    """Proxy logout to the SSO server.

    Revokes the current access token.  Requires ``Authorization: Bearer``.
    """
    auth_header = request.headers.get("authorization")

    return await _sso_proxy_post(
        "/sso/auth/logout",
        auth=auth_header,
        label="Logout",
    )


@router.post(
    "/logout-all",
    summary="Logout all sessions (revoke all tokens)",
    responses={
        200: {"description": "All tokens revoked — all sessions ended"},
        401: {"description": "Missing or invalid Bearer token"},
        502: {"description": "SSO server unreachable"},
    },
)
async def sso_logout_all(request: Request):
    """Proxy logout-all to the SSO server.

    Revokes all access and refresh tokens.  Requires ``Authorization: Bearer``.
    """
    auth_header = request.headers.get("authorization")

    return await _sso_proxy_post(
        "/sso/auth/logout-all",
        auth=auth_header,
        label="Logout-all",
    )
