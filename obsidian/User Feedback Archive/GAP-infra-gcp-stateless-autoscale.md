---
tags:
  - user-feedback
  - gap-ticket
status: resolved
priority: critical
domain: infrastructure
created: 2026-04-12
---

# [GAP] Application Not Fully Stateless for GCP Auto-Scale

> The application is ~85% stateless-ready but has 3 critical/high issues that must be fixed before deploying behind GCP auto-scaling: Slack token refresh race condition, startup recovery races, and local file system writes.

---

## Context

- **Discovered by**: Agent (architecture audit)
- **Discovered during**: Statelessness review for GCP auto-scale readiness
- **Related page(s)**: [[Architecture/Project Overview]], [[Integrations/Slack Integration]]

---

## Audit Summary: What's Already Stateless (Good)

| Area | Status | Notes |
|------|--------|-------|
| MongoDB as source of truth | ✅ | All jobs, PRDs, sessions, tokens persisted to DB |
| API routes | ✅ | Stateless, no global state in handlers |
| PRD flow execution | ✅ | Resumable from DB; transient in-memory state only during active stage |
| SSO/Auth | ✅ | JWT/DB-backed sessions, no in-memory session store |
| Job/run tracking | ✅ | `run_id`/`job_id` tracked in MongoDB, not in-memory |
| HTTP clients | ✅ | Created per-request, no shared state |
| No WebSockets | ✅ | All HTTP-based |
| No sticky sessions needed | ✅ | Any instance can serve any request |
| Health check endpoint | ✅ | `/health` returns JSON with liveness + service status |
| CrewAI agents | ✅ | Stateless between invocations |
| Knowledge files | ✅ | Read-only, bundled in container image |

---

## Current Behaviour

### Issue 1: CRITICAL — Slack Token Refresh Race Condition

**Files:**
- `src/crewai_productfeature_planner/tools/token_refresh_scheduler.py` — background daemon thread
- `src/crewai_productfeature_planner/tools/slack_token_manager.py` — `_cache`, `get_valid_token()`, refresh logic
- `src/crewai_productfeature_planner/mongodb/slack_oauth/repository.py` — `update_tokens()` uses `$set` with no CAS

Slack rotating tokens have **single-use refresh tokens**. If two instances refresh the same token simultaneously, one succeeds and the other permanently invalidates the token pair. Recovery requires manual reinstall of the Slack app for that workspace.

Each instance runs its own scheduler (every 30 min). All instances read the same refresh token from MongoDB. No distributed locking, no compare-and-swap, no version field.

### Issue 2: HIGH — Startup Recovery Race Conditions

**Files:**
- `src/crewai_productfeature_planner/main.py` — startup logic: `_mark_incomplete_jobs_as_failed`, `_generate_missing_outputs`, startup delivery thread
- `src/crewai_productfeature_planner/orchestrator/_startup_review.py` — discovers unpublished PRDs → publishes to Confluence
- `src/crewai_productfeature_planner/orchestrator/_startup_delivery.py` — discovers undelivered PRDs → creates Jira tickets

When multiple instances start simultaneously (e.g., during auto-scale up), each runs startup recovery independently causing duplicate Confluence publishes, duplicate Jira tickets, and race conditions on marking jobs as failed.

### Issue 3: MEDIUM — Local File System Writes (output/)

**Files:**
- `output/prds/<run_id>/` — PRD markdown/HTML files written on completion
- `output/<uuid>/` — other output artifacts
- Startup recovery regenerates missing output files from MongoDB

In a containerized/auto-scaled environment, local disk is ephemeral. Output files are lost on instance termination. MongoDB is the source of truth and can regenerate files, but wastes CPU on each new instance.

### Issue 4: LOW — Log Files Written Locally

**Files:**
- `src/crewai_productfeature_planner/scripts/logging_config.py`
- `logs/crewai.log.*`

Logs written to local `logs/` directory are split across instances and lost on termination.

### Issue 5: LOW — Per-Instance In-Memory Token Cache

**Files:**
- `src/crewai_productfeature_planner/tools/slack_token_manager.py` — `_cache: dict[str, dict[str, Any]]`

Each instance maintains its own Slack token cache. Not a correctness issue but causes redundant MongoDB reads after scale-up events.

---

## Expected Behaviour

- Application must be fully stateless and safe to run as multiple concurrent instances behind GCP auto-scaling
- No race conditions on shared resources (tokens, publishing, ticketing)
- No dependency on local filesystem for correctness
- Logs aggregated centrally via GCP Cloud Logging
- Health checks usable by GCP load balancer

---

## Affected Area

- [x] Configuration / Environment
- [x] API endpoint (missing / incomplete / wrong response)
- [x] Database schema (missing field / index / collection)
- [ ] Slack integration (missing intent / button / handler)
- [ ] Web app (missing page / component / flow)
- [ ] Agent / Flow (missing step / wrong output)
- [ ] Documentation (missing / outdated)

---

## Implementation Phases

### Phase 1: Critical Fixes (must do before multi-instance)
1. Fix Slack token refresh race — add CAS guard
2. Fix startup recovery races — atomic claim pattern
3. Add idempotency to Confluence/Jira delivery

### Phase 2: Cloud-Ready Infrastructure
4. Handle output file storage for stateless containers
5. Configure cloud-ready logging
6. Dockerize the application

### Phase 3: Deployment Configuration
7. Cloud Run / GKE service definition
8. MongoDB Atlas network config (VPC peering)

---

## Verification

1. Token refresh safety: two concurrent refresh attempts → only one succeeds
2. Startup recovery safety: two instances starting → no duplicate deliveries
3. Statelessness test: kill instance mid-flow → new instance resumes from DB
4. Multi-instance load test: 2+ instances → no conflicts or duplicates
5. Health check: `/health` works for GCP probes

---

## Decisions

> See [[QUESTIONS-gcp-stateless-autoscale]] for open questions requiring user input.

---

## Resolution

**Resolved in v0.70.0** (2026-04-12)

1. **Q1 (CAS Guard + Leader Lease)** — Already implemented in v0.69.0
2. **Q2 (Atomic Claim + Idempotency)** — Added `claim_for_confluence()`, `claim_for_jira()`, `release_claim()` to productRequirements repo. Publishing scheduler now claims work items atomically before processing.
3. **Q3 (Direct GCS Writes)** — New `output_storage.py` module. PRDFileWriteTool and UX design flow upload to GCS when `GCS_OUTPUT_BUCKET` is set. `google-cloud-storage` added as optional dep `[gcs]`.
4. **Q4 (Stdout JSON Logging)** — Already implemented in v0.69.0
5. **Q5 (Cloud Run + Cloud Tasks)** — Dockerfile, .dockerignore, cloudrun-service.yaml created with auto-scaling, health probes, and secret management.
