"""SSO authentication router — OAuth2 login, registration, and token management.

Proxies authentication requests to the C9 Single Sign-On service so
that the frontend only communicates with the Idea Foundry API.

Endpoints:
    GET  /auth/sso/login              — OAuth2 redirect to SSO
    POST /auth/sso/login              — Direct email/password login
    POST /auth/sso/login/verify-2fa   — Complete login with 2FA code
    POST /auth/sso/google             — Google Sign-In (ID token → JWT)
    GET  /auth/sso/register           — Redirect to SSO registration
    POST /auth/sso/register           — Direct registration
    POST /auth/sso/register/verify-2fa — Verify email 2FA code
    POST /auth/sso/register/resend-2fa — Resend registration 2FA code
    GET  /auth/sso/callback           — OAuth2 callback (code → tokens)
    GET  /auth/sso/status             — Check SSO auth status
    GET  /auth/sso/userinfo           — Get SSO user profile (Bearer)
    POST /auth/sso/password-reset         — Request password reset
    POST /auth/sso/password-reset/confirm — Confirm password reset
    POST /auth/sso/token/refresh      — Refresh access token
    POST /auth/sso/reauth             — Re-authenticate (Bearer + password)
    POST /auth/sso/reauth/verify-2fa  — Verify re-auth 2FA code
    POST /auth/sso/logout             — Revoke current token (Bearer)
    POST /auth/sso/logout-all         — Revoke all sessions (Bearer)
"""

from crewai_productfeature_planner.apis.sso.router import router

__all__ = ["router"]
