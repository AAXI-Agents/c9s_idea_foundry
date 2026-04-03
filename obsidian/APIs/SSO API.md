---
tags:
  - api
  - endpoints
  - sso
  - auth
aliases:
  - SSO API
  - SSO Endpoints
  - Single Sign-On API
---

# SSO API (C9S Single Sign-On)

> [!abstract] Summary
> Full C9S SSO integration using RS256 JWT middleware.
> Provides OAuth2 login, direct email/password login, registration,
> password reset, token refresh, re-authentication, Google Sign-In,
> and logout. All endpoints proxy requests to the SSO server — no
> credentials are stored locally.

**Source:** `src/crewai_productfeature_planner/apis/sso/router.py`
**Tag:** `SSO`
**Base path:** `/auth/sso`

---

## Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/auth/sso/login` | Start SSO sign-in (OAuth2 redirect) | None |
| `POST` | `/auth/sso/login` | Direct login — credentials → tokens or 2FA challenge | None |
| `POST` | `/auth/sso/login/verify-2fa` | Complete login with 2FA code → tokens | None |
| `POST` | `/auth/sso/google` | Google Sign-In — ID token → JWT tokens | None |
| `GET` | `/auth/sso/register` | Redirect to SSO registration page | None |
| `POST` | `/auth/sso/register` | Register — create account → 2FA challenge | None |
| `POST` | `/auth/sso/register/verify-2fa` | Verify registration email code | None |
| `POST` | `/auth/sso/register/resend-2fa` | Resend registration 2FA code | None |
| `GET` | `/auth/sso/callback` | OAuth2 callback — exchange code for tokens | None |
| `GET` | `/auth/sso/status` | Check SSO authentication status | Optional Bearer |
| `GET` | `/auth/sso/userinfo` | Get SSO user profile | Bearer required |
| `POST` | `/auth/sso/password-reset` | Request a password reset email | None |
| `POST` | `/auth/sso/password-reset/confirm` | Confirm password reset with 2FA code | None |
| `POST` | `/auth/sso/token/refresh` | Refresh access token | None |
| `POST` | `/auth/sso/reauth` | Re-auth step 1 — password → 2FA challenge | Bearer required |
| `POST` | `/auth/sso/reauth/verify-2fa` | Re-auth step 2 — verify 2FA code | Bearer required |
| `POST` | `/auth/sso/logout` | Revoke current token | Bearer required |
| `POST` | `/auth/sso/logout-all` | Revoke all tokens / sessions | Bearer required |

---

## `GET /auth/sso/login`

Redirects to the C9S SSO authorization endpoint (OAuth2 Authorization Code flow).

### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `redirect_after` | `string` | No | URL to redirect after successful login (default: `/`) |

### Response

HTTP 307 redirect to `{SSO_BASE_URL}/sso/oauth/authorize`.

### Security

- `redirect_after` is validated against same-origin policy to prevent open redirect attacks

---

## `POST /auth/sso/login`

Direct email/password login proxied to the SSO server.

### Request Body

```json
{
  "email": "user@example.com",
  "password": "MyPassword123"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | `string` | **Yes** | User's email address |
| `password` | `string` | **Yes** | User's password |

### Response (2FA disabled)

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIs...",
  "refresh_token": "rt-abc123",
  "token_type": "Bearer",
  "expires_in": 900,
  "enterprise_id": "ent-001",
  "organization_id": "org-001"
}
```

### Response (2FA enabled)

```json
{
  "two_factor_required": true,
  "login_token": "lt-abc123",
  "email": "user@example.com",
  "expires_in": 300
}
```

---

## `POST /auth/sso/login/verify-2fa`

Complete login by verifying the 2FA code received via email.

### Request Body

```json
{
  "email": "user@example.com",
  "login_token": "lt-abc123",
  "code": "123456"
}
```

### Response

Same token response as direct login (2FA disabled case).

---

## `POST /auth/sso/google`

Google Sign-In — exchange a Google ID token for JWT tokens.

### Request Body

```json
{
  "id_token": "eyJhbGci..."
}
```

### Response

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIs...",
  "refresh_token": "rt-abc123",
  "token_type": "Bearer",
  "expires_in": 900,
  "is_new_user": false
}
```

---

## `GET /auth/sso/register`

Redirects to the C9S SSO user registration page.

### Response

HTTP 307 redirect to `{SSO_BASE_URL}/sso/users/register`.

---

## `POST /auth/sso/register`

Register a new user account. Sends a 2FA verification code via email.

### Request Body

```json
{
  "email": "user@example.com",
  "password": "MinLength8"
}
```

### Response (201)

```json
{
  "user_id": "uid-abc123",
  "email": "newuser@example.com",
  "two_factor_required": true
}
```

---

## `POST /auth/sso/register/verify-2fa`

Verify the registration email code to activate the account.

### Request Body

```json
{
  "email": "user@example.com",
  "code": "123456"
}
```

---

## `POST /auth/sso/register/resend-2fa`

Resend the registration 2FA code.

### Request Body

```json
{
  "email": "user@example.com"
}
```

---

## `GET /auth/sso/callback`

Handles the OAuth2 callback from C9S SSO. Exchanges the authorization code for tokens.

### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `code` | `string` | Yes | Authorization code from SSO |
| `state` | `string` | Yes | CSRF state parameter |
| `error` | `string` | No | Error code if authorization failed |

### Response

HTML page showing success (with auto-redirect) or failure.

---

## `GET /auth/sso/status`

Returns current SSO authentication status.

### Response

```json
{
  "authenticated": true,
  "user_id": "usr_abc123",
  "email": "user@example.com",
  "roles": ["admin"]
}
```

Or when not authenticated:

```json
{
  "authenticated": false,
  "sso_configured": true
}
```

---

## `GET /auth/sso/userinfo`

Returns the SSO user profile. Requires `Authorization: Bearer {token}` header.

### Response

```json
{
  "user_id": "usr_abc123",
  "email": "user@example.com",
  "roles": ["admin"],
  "enterprise_id": "ent-001",
  "organization_id": "org-001"
}
```

---

## `POST /auth/sso/password-reset`

Request a password reset email.

### Request Body

```json
{
  "email": "user@example.com"
}
```

---

## `POST /auth/sso/password-reset/confirm`

Confirm password reset with the 2FA code and new password.

### Request Body

```json
{
  "email": "user@example.com",
  "code": "123456",
  "new_password": "NewP@ss1"
}
```

---

## `POST /auth/sso/token/refresh`

Refresh an expired access token using a refresh token.

### Request Body

```json
{
  "refresh_token": "rt-abc123"
}
```

### Response

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIs...",
  "refresh_token": "rt-new-abc123",
  "token_type": "Bearer",
  "expires_in": 900
}
```

---

## `POST /auth/sso/reauth`

Re-authenticate for sensitive operations. Requires Bearer token AND password.

### Request Body

```json
{
  "password": "CurrentPassword"
}
```

### Response

```json
{
  "two_factor_required": true,
  "login_token": "reauth-lt-abc123",
  "email": "user@example.com",
  "expires_in": 300
}
```

---

## `POST /auth/sso/reauth/verify-2fa`

Verify re-authentication 2FA code. Requires Bearer token.

### Request Body

```json
{
  "reauth_token": "reauth-lt-abc123",
  "code": "123456"
}
```

---

## `POST /auth/sso/logout`

Revoke the current access token. Requires `Authorization: Bearer` header.

---

## `POST /auth/sso/logout-all`

Revoke all access and refresh tokens for the user. Requires `Authorization: Bearer` header.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SSO_BASE_URL` | Yes | C9S SSO server URL (default: `http://localhost:8100`) |
| `SSO_CLIENT_ID` | Yes | OAuth client ID registered for Idea Foundry |
| `SSO_CLIENT_SECRET` | Yes | OAuth client secret |
| `SSO_ENABLED` | No | Enable/disable SSO auth enforcement (default: `false`) |
| `SSO_JWT_PUBLIC_KEY_PATH` | No | Path to RS256 PEM public key for JWT validation |
| `SSO_ISSUER` | No | Expected JWT issuer claim (default: `c9s-sso`) |
| `SSO_EXPECTED_APP_ID` | No | Expected `app_id` claim in JWT tokens |

---

## Related

- [[SSO Webhooks/]] — SSO lifecycle webhook events
- [[API Overview]] — Full API index
- [[Environment Variables]] — All env vars

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
