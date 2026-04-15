---
tags:
  - user-feedback
  - gap-ticket
status: open
priority: high
domain: web-app
created: 2026-04-14
related: GAP-multi-tenancy-data-isolation
---

# [GAP] Web App — Tenant Context in All API Calls

> Web app must send JWT with enterprise_id/organization_id claims, and UI must scope all data views to the user's tenant.

---

## Context

- **Discovered by**: Agent (during multi-tenancy design)
- **Discovered during**: Multi-tenancy implementation planning
- **Related page(s)**: [[QUESTIONS-multi-tenancy-design]]

---

## Current Behaviour

- Web app sends JWT Bearer token on API calls but does NOT rely on tenant scoping
- All data from all orgs is visible in every view (projects list, ideas list, dashboard)
- No org/enterprise selector or indicator in the UI

---

## Expected Behaviour

1. **Project list** (`GET /projects`) — only shows projects for the user's organization
2. **Ideas list** (`GET /ideas`) — only shows ideas for the user's org
3. **Dashboard stats** (`GET /dashboard/stats`) — aggregates only the user's org data
4. **PRD flow views** — only shows flows belonging to the user's org
5. **Org indicator** — header/nav shows which organization the user belongs to
6. **Enterprise admin view** — if user has `enterprise_admin` role, show an org switcher/filter to view data across all orgs in the enterprise

---

## Acceptance Criteria

- [ ] All API calls include JWT with `enterprise_id` and `organization_id` claims
- [ ] Project list is scoped to user's org (verify no cross-org data leaks)
- [ ] Ideas list is scoped to user's org
- [ ] Dashboard stats reflect only user's org
- [ ] Organization name displayed in header/nav
- [ ] Enterprise admins see an org filter/switcher (optional for v1 — can be follow-up)

---

## Affected Area

- [ ] API endpoint (missing / incomplete / wrong response)
- [ ] Database schema (missing field / index / collection)
- [ ] Slack integration (missing intent / button / handler)
- [x] Web app (missing page / component / flow)
- [ ] Agent / Flow (missing step / wrong output)
- [ ] Documentation (missing / outdated)
- [ ] Configuration / Environment

---

## Resolution

**Implemented** (2026-04-14) — Frontend multi-tenancy support added:

1. `User` model in `AuthContext` extended with `roles`, `enterprise_id`, `organization_id`, `enterprise_name`, `organization_name`
2. `UserProfile` in `authService` updated with `enterprise_name` and `organization_name` fields
3. `TenantContext` created — manages selected org state for enterprise admins, persists in localStorage
4. API interceptor in `api.ts` now injects `organization_id` query param from tenant context (skips admin endpoints)
5. `OrgSwitcher` component in sidebar shows org name for non-admins, full dropdown for enterprise admins
6. All data views are tenant-scoped via the API interceptor — projects, ideas, dashboard, flows

**Backend dependency**: Requires `/admin/organizations` endpoint and `organization_id` query param support on existing endpoints.
