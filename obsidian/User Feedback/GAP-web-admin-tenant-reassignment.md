---
tags:
  - user-feedback
  - gap-ticket
status: open
priority: medium
domain: web-app
created: 2026-04-14
related: GAP-multi-tenancy-data-isolation
---

# [GAP] Web App — Admin Tenant Reassignment UI

> Admin users need a UI to reassign projects (and all related data) from one organization to another.

---

## Context

- **Discovered by**: Agent (during multi-tenancy design)
- **Discovered during**: Multi-tenancy implementation planning — Decision 3 (Backfill Default + API for Reassignment)
- **Related page(s)**: [[QUESTIONS-multi-tenancy-design]]

---

## Current Behaviour

- No UI for managing project-to-org assignments
- After migration, all existing data will be in a "default" organization
- No way to move projects between organizations

---

## Expected Behaviour

1. **Admin settings page** — accessible to `enterprise_admin` role users
2. **Project reassignment view** — shows all projects with their current org assignment
3. **Reassign action** — dropdown to select target org, confirmation dialog
4. **Cascade indicator** — shows how many related documents (ideas, jobs, PRDs) will be moved
5. **Audit log** — records who reassigned what, when

---

## Backend API Support

- `PATCH /admin/projects/{project_id}/tenant` — reassign a project to a different org
  - Cascades `enterprise_id` + `organization_id` to: workingIdeas, crewJobs, productRequirements, projectMemory, agentInteraction, userSuggestions
  - Returns count of cascaded documents
- `GET /admin/projects` — list all projects with org info (enterprise_admin only, cross-org)

---

## Acceptance Criteria

- [ ] Admin page lists all projects with current org assignment
- [ ] Dropdown allows selecting target organization
- [ ] Confirmation dialog shows cascade impact (document counts)
- [ ] Reassignment cascades to all related collections
- [ ] Audit log entry created for each reassignment
- [ ] Only `enterprise_admin` role can access

---

## Affected Area

- [x] API endpoint (missing / incomplete / wrong response)
- [ ] Database schema (missing field / index / collection)
- [ ] Slack integration (missing intent / button / handler)
- [x] Web app (missing page / component / flow)
- [ ] Agent / Flow (missing step / wrong output)
- [ ] Documentation (missing / outdated)
- [ ] Configuration / Environment

---

## Resolution

**Implemented** (2026-04-14) — Admin tenant reassignment UI added:

1. Admin page at `/admin` (`app/src/app/admin/page.tsx`) — accessible only to `enterprise_admin` role
2. Project table showing all cross-org projects with org badges, idea/job/PRD counts
3. Filter by organization dropdown
4. Reassignment dialog with target org selector + cascade preview (shows affected document counts)
5. `adminService.ts` (`app/src/services/adminService.ts`) — service stubs for:
   - `GET /admin/organizations`
   - `GET /admin/projects`
   - `GET /admin/projects/{id}/cascade-preview`
   - `PATCH /admin/projects/{id}/tenant`
6. Full i18n support (English + Vietnamese)

**Backend dependency**: Requires all admin API endpoints to be implemented.
