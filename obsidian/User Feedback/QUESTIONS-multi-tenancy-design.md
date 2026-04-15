---
tags:
  - user-feedback
  - questions
status: resolved
created: 2026-04-14
resolved: 2026-04-14
related: GAP-multi-tenancy-data-isolation
---

# QUESTIONS — Multi-Tenancy Data Isolation Design

## Research Summary

### Current State (Critical Gaps)

**JWT tokens already carry tenant IDs but they are never used:**
- `require_sso_user()` extracts `enterprise_id` and `organization_id` from JWT claims (sso_auth.py lines 416-417)
- These values are returned in the user dict but **ignored by every API endpoint and every DB query**

**No collection has tenant fields:**

| Collection | Current scope | Fields used |
|---|---|---|
| `projectConfig` | Global (no scope) | `project_id` only |
| `workingIdeas` | `project_id`, `slack_channel` | No tenant fields |
| `productRequirements` | `run_id` only | No tenant fields |
| `crewJobs` | `job_id`, `run_id` | No tenant fields |
| `agentInteraction` | `project_id`, `channel`, `user_id` | No tenant fields |
| `userSession` | `user_id`, `channel` | No tenant fields |
| `projectMemory` | `project_id` only | No tenant fields |
| `userSuggestions` | `project_id` only | No tenant fields |
| `slackOAuth` | `team_id` only | No enterprise/org fields |

**Impact**: Any authenticated user can see and modify ALL data from ALL organizations.

---

## Design Decisions Required

### Decision 1: Tenant Hierarchy Model

How should enterprise and organization relate?

- [ ] **Option A — Two-Level Hierarchy (Enterprise → Organization)**
  - `enterprise_id` = corporate parent account (e.g., "Acme Corp")
  - `organization_id` = subsidiary/division (e.g., "Acme Engineering", "Acme Marketing")
  - Enterprise users see all orgs under their enterprise
  - Org users see only their own org's data
  - **Pro**: Clean separation, supports large enterprises with multiple divisions
  - **Con**: More complex queries (need to check both fields)

- [ ] **Option B — Single-Level (Organization Only)**
  - `organization_id` = the only tenant boundary
  - No enterprise concept — each org is fully isolated
  - Admin users within an org can see all org data
  - **Pro**: Simpler schema and queries
  - **Con**: No corporate visibility across divisions; would need a separate "enterprise view" feature later

- [ ] **Option C — Three-Level (Enterprise → Organization → Team)**
  - Adds `team_id` within orgs for finer-grained isolation
  - **Pro**: Most granular control
  - **Con**: Over-engineered for current needs; significant complexity

- [x] **Suggested — Two-Level with Enterprise Override**
  - Same as Option A, BUT with a `role`-based override:
    - Users with `enterprise_id` set + role `enterprise_admin` → see all orgs in their enterprise
    - Users with only `organization_id` → see only their org
    - Enterprise admins can also filter by specific org when needed
  - **Pro**: Clean hierarchy, role-based visibility, supports both corporate and org views
  - **Con**: Slightly more complex than Option A (role check), but more flexible

---

### Decision 2: Query Enforcement Strategy

How should tenant filtering be enforced in MongoDB queries?

- [ ] **Option A — Repository-Level Filter Injection**
  - Create a `TenantContext` dataclass passed to every repository function
  - Each repository function adds `enterprise_id`/`organization_id` to its query
  - **Pro**: Explicit, easy to audit, each function clearly shows its filter
  - **Con**: Must update ~50 repository functions; risk of missing one

- [ ] **Option B — Middleware/Wrapper Pattern**
  - Create a `get_tenant_db()` that wraps `get_db()` and auto-injects tenant filters on every query
  - Uses MongoDB's `$and` to prepend tenant conditions to all queries
  - **Pro**: Single enforcement point; impossible to bypass
  - **Con**: Complex to implement correctly; may interfere with aggregation pipelines; harder to debug

- [ ] **Option C — MongoDB Views per Tenant**
  - Create filtered MongoDB views for each tenant at runtime
  - Repositories query views instead of base collections
  - **Pro**: Database-level enforcement; impossible to bypass in application code
  - **Con**: MongoDB Atlas free/shared tier may not support views efficiently; operational complexity managing views

- [x] **Suggested — Repository-Level with Shared Helper + Audit Test**
  - Create a `tenant_filter(user: dict) -> dict` helper that builds the correct filter based on user's enterprise_id, organization_id, and roles
  - Every repository function that reads or writes MUST call `tenant_filter()` to build its base query
  - Add a **regression test** that scans all repository functions and asserts they all include tenant filtering (similar to how Jira approval gate tests work)
  - **Pro**: Explicit like Option A, but with automated enforcement via test; single helper to maintain; easy to audit
  - **Con**: Still manual per-function, but the test catches misses

---

### Decision 3: Schema Migration Strategy

How should existing data be handled?

- [ ] **Option A — Backfill with Default Org**
  - Create a "default" enterprise and organization
  - Backfill ALL existing documents with the default org's IDs
  - All existing data appears under the default org
  - **Pro**: No data loss; existing users see their data immediately
  - **Con**: If there are already multiple real enterprises, their data gets merged into one default org

- [ ] **Option B — Backfill from Slack team_id Mapping**
  - Use existing `slackOAuth.team_id` to derive organization mapping
  - Map each Slack workspace to an organization
  - Backfill documents by tracing: slackOAuth → channel → workingIdeas → crewJobs → etc.
  - **Pro**: Preserves natural workspace boundaries
  - **Con**: Complex migration; not all data has Slack channel refs; CLI-created data has no team_id

- [ ] **Option C — Manual Mapping Script**
  - Create a migration script that prompts for enterprise/org assignment per project
  - Admin reviews each project and assigns it to the correct org
  - **Pro**: Most accurate; no assumptions
  - **Con**: Manual effort; blocks deployment

- [x] **Suggested — Backfill Default + API for Reassignment**
  - Backfill all existing data with a default enterprise/org (Option A)
  - Add an admin API endpoint (`PATCH /admin/projects/{id}/tenant`) to reassign projects to different orgs
  - When a project is reassigned, cascade the new `enterprise_id`/`organization_id` to all related documents (workingIdeas, crewJobs, productRequirements, etc.)
  - **Pro**: Quick deployment, no data loss, easy to fix assignments later
  - **Con**: Requires admin UI or API calls to clean up

---

### Decision 4: Slack Workspace to Organization Mapping

How should Slack workspaces map to organizations?

- [ ] **Option A — 1:1 Mapping (team_id = organization_id)**
  - Each Slack workspace IS an organization
  - Store `enterprise_id` + `organization_id` in `slackOAuth` during OAuth install
  - The installing user's JWT claims determine the org
  - **Pro**: Simple; natural fit since Slack workspaces are already org-scoped
  - **Con**: If multiple Slack workspaces belong to one org, they'd be split

- [ ] **Option B — Configurable Mapping Table**
  - New `tenantMapping` collection: `{ team_id, enterprise_id, organization_id }`
  - Admin configures which Slack workspace belongs to which org
  - **Pro**: Flexible; handles multi-workspace orgs and shared workspaces
  - **Con**: Extra collection; requires admin setup step

- [ ] **Option C — Derive from SSO at Runtime**
  - When Slack events arrive, look up the Slack user's SSO identity to get their org
  - **Pro**: Always accurate; no mapping table needed
  - **Con**: Requires SSO lookup on every Slack event; adds latency; users not in SSO can't use Slack bot

- [x] **Suggested — 1:1 Default + Override Table**
  - Default: `team_id` maps to the enterprise/org from the installing user's JWT
  - Store in `slackOAuth`: `{ team_id, enterprise_id, organization_id, ... }`
  - Allow admin override via API if a workspace needs different mapping
  - **Pro**: Zero config for simple cases; override available for complex cases
  - **Con**: Installing user determines the org (which is usually correct)

---

### Decision 5: Background Process Tenant Scoping

How should background processes (Confluence publisher, startup recovery) be scoped?

- [ ] **Option A — Global Scan with Per-Document Tenant Context**
  - Background jobs still scan all documents (like today)
  - When publishing/recovering, use the document's `enterprise_id`/`organization_id` to load the correct credentials
  - **Pro**: Simple; works without changing scheduler architecture
  - **Con**: Cross-tenant data is loaded into memory (even if processed correctly)

- [ ] **Option B — Per-Tenant Scheduling**
  - Run separate scheduler instances per enterprise/org
  - Each scheduler only queries its own tenant's data
  - **Pro**: Complete isolation; each tenant's jobs are independent
  - **Con**: Complex; scalability concern with many tenants

- [x] **Suggested — Global Scan + Tenant-Scoped Processing**
  - Keep the single global scan (find all pending items)
  - Group results by `enterprise_id` / `organization_id`
  - Process each group with that tenant's credentials and context
  - Add tenant context logging for audit trail
  - **Pro**: Simple architecture, correct isolation, good auditability
  - **Con**: All data in memory briefly (acceptable for current scale)

---

## Impact Summary

### Collections to Modify (Add `enterprise_id` + `organization_id` fields)

| Collection | New fields | New indexes |
|---|---|---|
| `projectConfig` | `enterprise_id`, `organization_id` | `(enterprise_id, 1), (organization_id, 1)` |
| `workingIdeas` | `enterprise_id`, `organization_id` | `(enterprise_id, 1), (organization_id, 1)` |
| `productRequirements` | `enterprise_id`, `organization_id` | `(organization_id, 1)` |
| `crewJobs` | `enterprise_id`, `organization_id` | `(organization_id, 1)` |
| `agentInteraction` | `enterprise_id`, `organization_id` | `(organization_id, 1)` |
| `userSession` | `enterprise_id`, `organization_id` | `(organization_id, 1)` |
| `projectMemory` | `enterprise_id`, `organization_id` | `(organization_id, 1)` |
| `userSuggestions` | `enterprise_id`, `organization_id` | `(organization_id, 1)` |
| `slackOAuth` | `enterprise_id`, `organization_id` | `(organization_id, 1)` |

### Repository Functions to Update (~50 functions across 9 repositories)

| Repository | Functions to update | CRUD |
|---|---|---|
| `project_config` | `create_project`, `get_project`, `list_projects`, `update_project`, `delete_project` | C/R/U/D |
| `working_ideas` | `find_ideas_by_project`, `find_completed_ideas_by_project`, `find_unfinalized`, `find_completed_without_confluence`, `find_completed_without_output`, `find_resumable_on_startup`, `fail_unfinalized_on_startup`, `find_recent_duplicate_idea`, `find_active_duplicate_idea`, `has_active_idea_flow`, `find_idea_by_thread`, `find_run_any_status`, `get_run_documents`, `_backfill_orphaned_ideas` | R/U |
| `product_requirements` | `get_delivery_record`, `upsert_delivery_record`, `find_pending_delivery`, `claim_for_confluence`, `claim_for_jira` | R/U |
| `crew_jobs` | `create_job`, `find_active_job`, `find_job`, `list_jobs`, `fail_incomplete_jobs_on_startup`, `archive_stale_jobs_on_startup` | C/R/U |
| `agent_interactions` | `log_interaction`, `find_interaction`, `find_by_source`, `find_by_intent`, `query_interactions` | C/R |
| `user_session` | `start_session`, `end_active_session`, `get_active_session`, `list_sessions`, `start_channel_session`, `end_channel_session`, `get_active_channel_session` | C/R/U |
| `project_memory` | `upsert_project_memory`, `get_project_memory`, `add_memory_entry`, `replace_category_entries`, `clear_category`, `delete_memory_entry` | C/R/U/D |
| `user_suggestions` | `log_suggestion`, `find_suggestions_by_project` | C/R |
| `slack_oauth` | `upsert_installation`, `get_installation`, `delete_installation` | C/R/D |

### API Endpoints to Update

All endpoints that use `Depends(require_sso_user)` must pass the user's tenant context to repository calls:
- `GET /projects`, `POST /projects`, `GET /projects/{id}`, `PATCH /projects/{id}`, `DELETE /projects/{id}`
- `GET /ideas`, `POST /ideas`
- `POST /slack/kickoff`, Slack event handlers
- `GET /user/profile`, `POST /user/profile`
- Dashboard endpoints
- Publishing endpoints

### Files to Create

- `src/.../mongodb/_tenant.py` — `TenantContext` dataclass + `tenant_filter()` helper
- `scripts/migrate_add_tenant_fields.py` — backfill migration script
- `tests/test_tenant_isolation.py` — regression test ensuring all queries include tenant filters

---

## Estimated Scope

| Phase | Description | Files |
|---|---|---|
| **Phase 1**: Schema + Helper | Add `TenantContext`, `tenant_filter()`, update `setup_mongodb.py` indexes | 2-3 new files |
| **Phase 2**: Repository Updates | Add tenant filtering to all ~50 repository functions | 9 repository files |
| **Phase 3**: API Layer | Pass user tenant context from API endpoints to repositories | 10-15 API files |
| **Phase 4**: Slack Integration | Map Slack workspace to org, inject tenant in flow handlers | 3-5 Slack files |
| **Phase 5**: Background Processes | Scope publisher scheduler, startup recovery | 2-3 files |
| **Phase 6**: Migration | Backfill script, data migration, index creation | 1-2 scripts |
| **Phase 7**: Tests | Tenant isolation regression tests, update all existing tests | 20+ test files |
