# API Overview

> Idea Foundry REST API — FastAPI backend powering both the Slack bot and web application.
> Each API domain has its own page with detailed request/response schemas and field-level documentation.

---

## API Pages

| Domain | Page | Endpoints | Auth |
|--------|------|-----------|------|
| **Health** | [[Health API]] | 5 | None (probes), SSO (token mgmt) |
| **Projects** | [[Projects API]] | 5 | SSO |
| **Ideas** | [[Ideas API]] | 3 | SSO |
| **PRD Flow** | [[PRD Flow API]] | 9 | SSO |
| **Publishing** | [[Publishing API]] | 9 | SSO |
| **Slack** | [[Slack API]] | 5 | Slack HMAC |
| **SSO Webhooks** | [[SSO Webhooks API]] | 1 | Webhook HMAC |

**Total**: 37 endpoints across 10 routers

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

1. `POST /flow/prd/kickoff` with `{ "idea": "My feature idea" }` → get `run_id`
2. Poll `GET /flow/runs/{run_id}` every 5s for progress
3. When `status = "awaiting_approval"`, show section for review
4. `POST /flow/prd/approve` with `{ "run_id": "...", "approve": true }` or `{ "approve": false, "feedback": "..." }`
5. Continue polling until `status = "completed"`
6. Optionally publish: `POST /publishing/confluence/{run_id}` and `POST /publishing/jira/{run_id}`

→ Full request/response details: [[PRD Flow API]]

---

## Router Mounting

All routers are registered in `apis/__init__.py`:

| Router | Prefix | Auth Dependency | Details |
|--------|--------|----------------|---------|
| health_router | — | None | [[Health API]] |
| prd_router | — | `require_sso_user` | [[PRD Flow API]] |
| projects_router | `/projects` | `require_sso_user` | [[Projects API]] |
| ideas_router | `/ideas` | `require_sso_user` | [[Ideas API]] |
| publishing_router | `/publishing` | `require_sso_user` | [[Publishing API]] |
| slack_router | — | `verify_slack_request` | [[Slack API]] |
| slack_events_router | — | `verify_slack_request` | [[Slack API]] |
| slack_interactions_router | — | `verify_slack_request` | [[Slack API]] |
| slack_oauth_router | — | None | [[Slack API]] |
| sso_webhooks_router | `/sso/webhooks` | `verify_sso_webhook` | [[SSO Webhooks API]] |

---

## Documentation

- OpenAPI specification: `docs/openapi/openapi.json`
- Swagger UI: Available at `/docs` when server is running
- All endpoints have typed Pydantic request/response schemas

---

See also: [[Slack Integration]], [[Project Overview]], [[Environment Variables]], [[Server Lifecycle]]
