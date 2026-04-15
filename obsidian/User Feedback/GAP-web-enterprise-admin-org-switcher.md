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

# [GAP] Web App — Enterprise Admin Org Switcher

> Enterprise admin users need an org selector to view/manage data across all organizations in their enterprise.

---

## Context

- **Discovered by**: Agent (during multi-tenancy design)
- **Discovered during**: Multi-tenancy implementation planning — Decision 1 (Two-Level with Enterprise Override)
- **Related page(s)**: [[QUESTIONS-multi-tenancy-design]]

---

## Current Behaviour

- No concept of enterprise vs organization in the UI
- No way for corporate users to switch between org views
- All users see identical global data

---

## Expected Behaviour

1. **Org switcher dropdown** — visible only to users with `enterprise_admin` role
2. Shows all organizations under the user's enterprise
3. **"All Organizations"** option shows aggregated data across all orgs
4. **Per-org selection** filters all views (projects, ideas, dashboard, flows) to that org
5. Selected org persists in session (localStorage or cookie)
6. Non-enterprise-admin users see only their own org with no switcher

---

## UI Component Spec

```
┌─────────────────────────────────────────┐
│  🏢 Acme Corp  ▾                        │  ← Enterprise name + dropdown
│  ┌─────────────────────┐                │
│  │  All Organizations  │  ← Shows all   │
│  │  ─────────────────  │                │
│  │  Acme Engineering   │  ← Filter to   │
│  │  Acme Marketing     │     this org   │
│  │  Acme Design        │                │
│  └─────────────────────┘                │
└─────────────────────────────────────────┘
```

---

## Backend API Support Needed

- `GET /admin/organizations` — list all orgs in the user's enterprise (enterprise_admin only)
- Query params on existing endpoints: `?organization_id=<id>` for enterprise admins to filter by org

---

## Acceptance Criteria

- [ ] Org switcher visible only to `enterprise_admin` role users
- [ ] Lists all orgs under the user's enterprise
- [ ] "All Organizations" option shows aggregated cross-org data
- [ ] Per-org selection filters projects, ideas, dashboard, flows
- [ ] Selected org persists across page navigations
- [ ] Non-admin users see no switcher — only their org data

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

**Implemented** (2026-04-14) — Enterprise admin org switcher added:

1. `OrgSwitcher` component (`app/src/components/OrgSwitcher.tsx`) — dropdown in sidebar header
2. For enterprise admins: shows enterprise name + dropdown listing all orgs + "All Organizations"
3. For non-admins: shows static org name indicator
4. `TenantContext` (`app/src/contexts/TenantContext.tsx`) — fetches orgs from `GET /admin/organizations`, manages selection, persists in localStorage
5. API interceptor injects `organization_id` into all non-admin API calls when a specific org is selected
6. Admin nav item in sidebar (shield icon) visible only to `enterprise_admin` role users

**Backend dependency**: Requires `GET /admin/organizations` endpoint and `organization_id` query param filtering on existing endpoints.
