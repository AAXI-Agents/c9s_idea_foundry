---
tags:
  - api
  - endpoints
---

# API Overview

> Idea Foundry REST API — FastAPI backend powering both the Slack bot and web application.
> Each API endpoint has its own page with detailed request/response schemas and database algorithm.

---

## API Domains

| Domain | Folder | Endpoints | Auth |
|--------|--------|-----------|------|
| **Health** | [[Health/]] | 5 | None (probes), SSO (token mgmt) |
| **Projects** | [[Projects/]] | 5 | SSO |
| **Ideas** | [[Ideas/]] | 3 | SSO |
| **PRD Flow** | [[PRD Flow/]] | 10 | SSO |
| **Publishing** | [[Publishing/]] | 9 | SSO |
| **Integrations** | [[Integrations/]] | 1 | SSO |
| **Slack** | [[Slack/]] | 5 | Slack HMAC |
| **SSO** | [[SSO API]] | 18 | None / Bearer |
| **SSO Webhooks** | [[SSO Webhooks/]] | 1 | Webhook HMAC |

**Total**: 57 endpoints across 12 routers

---

## Endpoint Index

### Health (5 endpoints)

| Endpoint | Page |
|----------|------|
| `GET /health` | [[Health/GET health]] |
| `GET /version` | [[Health/GET version]] |
| `GET /health/slack-token` | [[Health/GET health-slack-token]] |
| `POST /health/slack-token/exchange` | [[Health/POST health-slack-token-exchange]] |
| `POST /health/slack-token/refresh` | [[Health/POST health-slack-token-refresh]] |

### Dashboard (1 endpoint)

| Endpoint | Page |
|----------|------|
| `GET /dashboard/stats` | — |

### Projects (5 endpoints)

| Endpoint | Page |
|----------|------|
| `GET /projects` | [[Projects/GET projects]] |
| `GET /projects/{project_id}` | [[Projects/GET projects-{project_id}]] |
| `POST /projects` | [[Projects/POST projects]] |
| `PATCH /projects/{project_id}` | [[Projects/PATCH projects-{project_id}]] |
| `DELETE /projects/{project_id}` | [[Projects/DELETE projects-{project_id}]] |

### Ideas (3 endpoints)

| Endpoint | Page |
|----------|------|
| `GET /ideas` | [[Ideas/GET ideas]] |
| `GET /ideas/{run_id}` | [[Ideas/GET ideas-{run_id}]] |
| `PATCH /ideas/{run_id}/status` | [[Ideas/PATCH ideas-{run_id}-status]] |

### PRD Flow (14 endpoints)

| Endpoint | Page |
|----------|------|
| `POST /flow/prd/kickoff` | [[PRD Flow/POST flow-prd-kickoff]] |
| `POST /flow/prd/approve` | [[PRD Flow/POST flow-prd-approve]] |
| `POST /flow/prd/pause` | [[PRD Flow/POST flow-prd-pause]] |
| `POST /flow/prd/resume` | [[PRD Flow/POST flow-prd-resume]] |
| `GET /flow/runs/{run_id}` | [[PRD Flow/GET flow-runs-{run_id}]] |
| `GET /flow/runs/{run_id}/activity` | [[PRD Flow/GET flow-runs-{run_id}-activity]] |
| `GET /flow/runs` | [[PRD Flow/GET flow-runs]] |
| `GET /flow/prd/resumable` | [[PRD Flow/GET flow-prd-resumable]] |
| `GET /flow/jobs` | [[PRD Flow/GET flow-jobs]] |
| `GET /flow/jobs/{job_id}` | [[PRD Flow/GET flow-jobs-{job_id}]] |
| `POST /flow/ux-design/{run_id}` | — |
| `POST /flow/ux/kickoff` | — |
| `GET /flow/ux/status/{run_id}` | — |
| `WS /flow/runs/{run_id}/ws` | — |

### Publishing (9 endpoints)

| Endpoint | Page |
|----------|------|
| `GET /publishing/pending` | [[Publishing/GET publishing-pending]] |
| `POST /publishing/confluence/{run_id}` | [[Publishing/POST publishing-confluence-{run_id}]] |
| `POST /publishing/confluence/all` | [[Publishing/POST publishing-confluence-all]] |
| `POST /publishing/jira/{run_id}` | [[Publishing/POST publishing-jira-{run_id}]] |
| `POST /publishing/jira/all` | [[Publishing/POST publishing-jira-all]] |
| `POST /publishing/all` | [[Publishing/POST publishing-all]] |
| `POST /publishing/all/{run_id}` | [[Publishing/POST publishing-all-{run_id}]] |
| `GET /publishing/status/{run_id}` | [[Publishing/GET publishing-status-{run_id}]] |
| `GET /publishing/automation/status` | [[Publishing/GET publishing-automation-status]] |

### Integrations (1 endpoint)

| Endpoint | Page |
|----------|------|
| `GET /integrations/status` | [[Integrations/GET integrations-status]] |

### Slack (5 endpoints)

| Endpoint | Page |
|----------|------|
| `POST /slack/kickoff` | [[Slack/POST slack-kickoff]] |
| `POST /slack/kickoff/sync` | [[Slack/POST slack-kickoff-sync]] |
| `POST /slack/events` | [[Slack/POST slack-events]] |
| `POST /slack/interactions` | [[Slack/POST slack-interactions]] |
| `GET /slack/oauth/callback` | [[Slack/GET slack-oauth-callback]] |

### SSO (18 endpoints)

| Endpoint | Description |
|----------|-------------|
| `GET /auth/sso/login` | Start SSO sign-in (OAuth2 redirect) |
| `POST /auth/sso/login` | Direct login — credentials → tokens or 2FA |
| `POST /auth/sso/login/verify-2fa` | Complete login with 2FA code |
| `POST /auth/sso/google` | Google Sign-In (ID token → JWT tokens) |
| `GET /auth/sso/register` | Redirect to SSO registration |
| `POST /auth/sso/register` | Register — create account → 2FA |
| `POST /auth/sso/register/verify-2fa` | Verify registration email code |
| `POST /auth/sso/register/resend-2fa` | Resend registration 2FA code |
| `GET /auth/sso/callback` | OAuth2 callback (code → tokens) |
| `GET /auth/sso/status` | Check SSO auth status |
| `GET /auth/sso/userinfo` | Get SSO user profile (Bearer) |
| `POST /auth/sso/password-reset` | Request password reset email |
| `POST /auth/sso/password-reset/confirm` | Confirm password reset |
| `POST /auth/sso/token/refresh` | Refresh access token |
| `POST /auth/sso/reauth` | Re-auth step 1 (Bearer + password) |
| `POST /auth/sso/reauth/verify-2fa` | Re-auth step 2 (verify code) |
| `POST /auth/sso/logout` | Revoke current token (Bearer) |
| `POST /auth/sso/logout-all` | Revoke all sessions (Bearer) |

See [[SSO API]] for detailed request/response schemas.

### SSO Webhooks (1 endpoint)

| Endpoint | Page |
|----------|------|
| `POST /sso/webhooks/events` | [[SSO Webhooks/POST sso-webhooks-events]] |

---

## Web App Integration Quick Start

### Authentication

All endpoints (except Health probes and Slack webhooks) require SSO Bearer token:
```
Authorization: Bearer <jwt_token>
```
When `SSO_ENABLED=false` (development mode), auth is bypassed with an anonymous user context.

**Auth Modes** (tried in order):
1. **Local RS256 JWT decode** — if `SSO_JWT_PUBLIC_KEY_PATH` is set (fast, no network)
2. **Remote introspection** — calls `SSO_BASE_URL/oauth/introspect` (fallback)

**User Auto-Provisioning**: On every authenticated request, the system ensures a local `users` collection record exists:
- SSO callers: matched by `sub` claim, then by email
- Slack callers: matched by `slack_user_id`, created from Slack profile

### CORS

Configured via `CORS_ALLOWED_ORIGINS` env var (defaults to `http://localhost:3000`). Set to your web app origin for cross-origin requests.

### Error Handling

All errors return a structured envelope:
```json
{
  "error_code": "LLM_ERROR | BILLING_ERROR | INTERNAL_ERROR",
  "message": "Human-readable description",
  "run_id": "affected run (if applicable)",
  "detail": "Additional diagnostic info"
}
```

HTTP status codes: 400 (validation), 401 (auth), 404 (not found), 409 (conflict), 422 (unprocessable), 500/503 (server error).

### Pagination

List endpoints (`/projects`, `/ideas`) support:
- `page` (1-based, default: 1)
- `page_size` (10, 25, or 50; default: 10)

Responses include: `items`, `total`, `page`, `page_size`, `total_pages`.

---

## Typical Web App Flow

1. `POST /flow/prd/kickoff` with `{ "idea": "My feature idea", "title": "Feature Title", "project_id": "proj-abc123" }` → get `run_id`
2. Poll `GET /flow/runs/{run_id}` every 5s for progress
3. When `status = "awaiting_approval"`, show section for review
4. `POST /flow/prd/approve` with `{ "run_id": "...", "approve": true }` or `{ "approve": false, "feedback": "..." }`
5. Continue polling until `status = "completed"`
6. Optionally publish: `POST /publishing/confluence/{run_id}` and `POST /publishing/jira/{run_id}`

→ Full request/response details: [[PRD Flow/POST flow-prd-kickoff]]

---

## Router Mounting

All routers are registered in `apis/__init__.py`:

| Router | Prefix | Auth Dependency | Details |
|--------|--------|----------------|---------|
| health_router | — | None | [[Health/]] |
| prd_router | — | `require_sso_user` | [[PRD Flow/]] |
| projects_router | `/projects` | `require_sso_user` | [[Projects/]] |
| ideas_router | `/ideas` | `require_sso_user` | [[Ideas/]] |
| publishing_router | `/publishing` | `require_sso_user` | [[Publishing/]] |
| integrations_router | `/integrations` | `require_sso_user` | [[Integrations/]] |
| slack_router | — | `verify_slack_request` | [[Slack/]] |
| slack_events_router | — | `verify_slack_request` | [[Slack/]] |
| slack_interactions_router | — | `verify_slack_request` | [[Slack/]] |
| slack_oauth_router | — | None | [[Slack/]] |
| sso_webhooks_router | `/sso/webhooks` | `verify_sso_webhook` | [[SSO Webhooks/]] |

---

## Documentation

- OpenAPI specification: `docs/openapi/openapi.json`
- Swagger UI: Available at `/docs` when server is running
- All endpoints have typed Pydantic request/response schemas

---

See also: [[Slack Integration]], [[Project Overview]], [[Environment Variables]], [[Server Lifecycle]]


---

## Change Requests

<!-- 
HOW TO USE: Add your change requests below as bullet points.
Codex will implement each request, update this page, bump the
version, and move the completed item to the "Completed" list.

FORMAT:

EXAMPLE:
-->

### Pending

_No pending change requests._

### Completed

_No completed change requests._
