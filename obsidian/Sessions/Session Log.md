---
tags:
  - sessions
---

# Session Log

> AI agent session tracking. Every new session or iteration appends an entry.

---

## Session — 2026-04-11 (v0.68.1)

**Focus**: Fix GET /ideas/ 500 error — ux_design_status None crash

### Root Cause
`idea_fields()` in `apis/ideas/models.py` used `doc.get("ux_design_status", "") or doc.get("figma_design_status", "")`. When both fields are `None` in MongoDB (not missing — explicitly null), the `or` chain evaluates to `None`, which Pydantic rejects for the `str` field.

### Fix
Added trailing `or ""` to guarantee a string result regardless of null combinations.

### Files Changed
- `apis/ideas/models.py` — `idea_fields()` trailing `or ""` on ux_design_status
- `tests/apis/ideas/test_router.py` — 6 regression tests (router + unit)

### Results
- 24 ideas API tests pass
- Version bumped to 0.68.1

---

## Session — 2026-04-11 (v0.68.0)

**Focus**: Stale project cleanup & duplicate-idea protection (GAP ticket resolution)

### User Decisions (from GAP-stale-project-proj1-cleanup.md)
- **R1+R2+R3**: All three — create cleanup script with archive and delete modes
- **S1**: Option A — reject duplicates with 409 (24h cooldown)

### Changes Applied
1. **Cleanup script** (`scripts/cleanup_orphan_projects.py`): CLI tool to find orphaned project_id refs. Modes: `--archive` (R1), `--delete` (R2), dry-run default (R3). Supports `--project <id>` filter and `--yes` for non-interactive
2. **Duplicate-idea cooldown** (S1A): `find_recent_duplicate_idea()` queries by `idea_normalized` + `project_id` within 24h window. API returns 409, Slack sends warning and returns early
3. **`idea_normalized` field**: Set by `save_project_ref()` and `save_slack_context()` — lowercase + whitespace-collapsed copy of idea text

### Files Changed
- `scripts/cleanup_orphan_projects.py` — NEW, standalone CLI with lazy imports
- `mongodb/working_ideas/_queries.py` — `find_recent_duplicate_idea()`, `_normalize_idea_text()`, `DUPLICATE_IDEA_COOLDOWN_HOURS`
- `mongodb/working_ideas/_status.py` — `_normalize_idea()`, `idea_normalized` field in save_project_ref/save_slack_context
- `mongodb/working_ideas/repository.py` + `__init__.py` — re-exports
- `apis/prd/_route_actions.py` — 409 duplicate check after project_id validation
- `apis/slack/router.py` — duplicate check before job creation in `_run_slack_prd_flow()`

### Tests
- `tests/test_cleanup_orphan_projects.py` — 10 new tests (6 classes)
- `tests/apis/prd/test_prd.py` — 3 new tests (duplicate scenarios)
- `tests/mongodb/working_ideas/test_repository.py` — 10 new tests (duplicate + normalized)

### GAP Ticket
- `GAP-stale-project-proj1-cleanup.md` — all items resolved → status: resolved

### Results
- 265 targeted tests pass (cleanup + PRD + repository)
- Version bumped to 0.68.0

---

## Session — 2026-04-10 (v0.64.0)

**Focus**: SSO GAP ticket resolution — remote-first validation + background key scheduler

### User Decisions (from GAP-sso-oauth-key-rotation-resilience.md)
- **R3**: Implement background key refresh scheduler (daemon thread, similar to token_refresh_scheduler.py)
- **S1**: Option B — remote-first validation (introspect is authoritative)

### Changes Applied
1. **Remote-first validation**: All SSO endpoints (`require_sso_user`, `/userinfo`, `/status`) now try remote introspection first, falling back to local RS256 decode when the SSO server is unreachable
2. **Background key refresh scheduler**: `start_key_refresh_scheduler()` — daemon thread that fetches JWKS/PEM every 6 hours + immediate on startup. Stops automatically with server. Configurable via `SSO_KEY_REFRESH_INTERVAL_SECONDS`
3. Scheduler auto-starts from `_lifespan` in `apis/__init__.py` (step 8c)

### Files Changed
- `apis/sso_auth.py` — remote-first flow in `require_sso_user`, added `start_key_refresh_scheduler/stop_key_refresh_scheduler/_key_refresh_loop`
- `apis/sso/router.py` — remote-first flow in `/userinfo` and `/status`
- `apis/__init__.py` — startup hook for key scheduler (step 8c)
- `tests/apis/sso/test_sso_router.py` — 3 new scheduler tests (48 total)

### GAP Ticket
- `GAP-sso-oauth-key-rotation-resilience.md` — all 4 items resolved → **deleted**

### Results
- 48 SSO tests pass, 2881 full regression green

---

## Session — 2026-04-10 (v0.63.3)

**Focus**: SSO auth fixes aligned with SSO server OpenAPI spec (v0.4.0)

### Root Cause (from SSO server docs review)
Fetched the SSO server's OpenAPI spec at `/sso/docs` and discovered 3 mismatches in our v0.63.2 implementation:

1. **Introspect auth method wrong** — We sent `Authorization: Bearer <client_secret>` header, but the SSO server's `IntrospectRequest` schema accepts `client_id` + `client_secret` **in the JSON body** (the Authorization header is for bearer access_token auth, not client_secret).
2. **Public key field name wrong** — We read `body.get("public_key")` but the SSO server returns `"public_key_pem"`.
3. **JWKS endpoint available** — SSO server already exposes `GET /.well-known/jwks.json` (standard RFC 7517). We weren't using it.

Also discovered: SSO server's refresh endpoint has a **10-second grace period** for concurrent requests, so concurrent refresh races are already handled server-side.

### Fixes Applied
1. `_introspect_remotely()` — removed `Authorization: Bearer` header, added `client_secret` to JSON body alongside `client_id`
2. `_fetch_and_save_public_key()` — now tries JWKS first (`/.well-known/jwks.json` with JWK→PEM conversion via `cryptography`), falls back to PEM endpoint (`/sso/oauth/public-key`) reading `public_key_pem` field
3. New `_fetch_jwks_pem()` + `_jwk_to_pem()` helpers — convert JWKS RSA key to PEM format using `RSAPublicNumbers`
4. New `_fetch_pem_directly()` — cleaner fallback to PEM endpoint

### Files Changed
- `apis/sso_auth.py` — introspect body auth, JWKS support, PEM field name fix
- `tests/apis/sso/test_sso_router.py` — updated introspect test (client_secret in body, no header), new JWKS test, updated PEM fallback test

### Results
- 45 SSO tests pass, 2878 full regression green

---

## Session — 2026-04-10 (v0.63.2)

**Focus**: SSO OAuth deep fix — 3-phase token validation with automatic key rotation recovery

### Root Cause (deeper, surfaced by v0.63.1 improved logging)
v0.63.1's enhanced error logging revealed the true SSO server error: `{'detail': 'Missing or invalid Authorization header'}`. The SSO introspection endpoint requires client credentials via **Authorization: Bearer &lt;client_secret&gt;** header, not just `client_id` in the JSON body. Additionally, the local RSA public key (`sso_public_key.pem`) has been stale since April 6, causing every local JWT decode to fail.

### Fixes Applied
1. `_introspect_remotely()` now sends `Authorization: Bearer <client_secret>` header per RFC 7662
2. New `_fetch_and_save_public_key()` — downloads current public key from `SSO_BASE_URL/sso/auth/public-key`, saves to disk, clears LRU cache
3. `require_sso_user`, `/userinfo`, and `/status` all use 3-phase validation: local decode → auto key fetch + retry → remote introspect
4. Seamless recovery from SSO key rotation without server restart

### Files Changed
- `apis/sso_auth.py` — Authorization header, `_fetch_and_save_public_key()`, 3-phase flow in `require_sso_user`
- `apis/sso/router.py` — imported `_fetch_and_save_public_key`, updated `/userinfo` and `/status` with 3-phase pattern
- `tests/apis/sso/test_sso_router.py` — updated TestIntrospectClientId (now checks Auth header), new TestFetchAndSavePublicKey (3 tests)

### Results
- 44 SSO tests pass, 2877 full regression green

---

## Session — 2026-04-10 (v0.63.1)

**Focus**: SSO userinfo 401 loop — investigate and fix OAuth error

### Root Cause
The `/auth/sso/userinfo` endpoint returned 401 even after a successful token refresh (200). Two concurrent issues:

1. **Missing `client_id` in introspection** — `_introspect_remotely()` sent `{"token": ...}` but the SSO server requires `client_id` for client authentication per RFC 7662. The `/token/refresh` endpoint worked because it already included `client_id`.
2. **Stale public key cache** — `_sso_public_key()` used `@lru_cache(maxsize=1)` which never re-read the key file. If the SSO server rotated its signing key (as shown by `InvalidSignatureError` on every JWT since April 6), local decode permanently failed.

### Fixes Applied
1. `_introspect_remotely()` now includes `SSO_CLIENT_ID` in the request body
2. `_decode_jwt_locally()` clears the `_sso_public_key` LRU cache on `InvalidSignatureError`
3. Introspection logs the response body on non-200 status (not just the status code)

### Files Changed
- `apis/sso_auth.py` — introspect client_id, cache clear, error logging
- `tests/apis/sso/test_sso_router.py` — 2 new tests (TestIntrospectClientId, TestPublicKeyCacheClear)

### Results
- 41 SSO tests pass, full regression green

---

## Session — 2026-04-10 (v0.63.0)

**Focus**: Implement 3 performance recommendations from GAP-api-projects-ideas-slow-latency

### Recommendations Implemented

1. **Motor async MongoDB driver** — `GET /ideas` and `GET /projects` now use native `await`-based Motor queries instead of `run_in_executor` + sync pymongo. Eliminates thread-pool overhead. New `mongodb/async_client.py` module provides `get_async_db()` for API endpoints while keeping sync pymongo for orchestrator/flow code.

2. **Response cache** — 5-second TTL in-memory cache (`apis/_response_cache.py`) for paginated list endpoints. Dashboard polling serves from cache instead of hitting Atlas on every request.

3. **Index coverage analysis script** — `scripts/explain_queries.py` runs `explain("executionStats")` on all API query paths and reports IXSCAN vs COLLSCAN status.

### User Decision
- **Suggestion (Option B)**: Keep current exclusion projection approach rather than MongoDB aggregation.

### Files Created
- `mongodb/async_client.py` — Motor AsyncIOMotorClient wrapper
- `apis/_response_cache.py` — TTL response cache
- `scripts/explain_queries.py` — Index analysis script
- `tests/apis/test_response_cache.py` — 7 cache tests
- `tests/mongodb/test_async_client.py` — 3 async client tests

### Files Changed
- `pyproject.toml` — added `motor>=3.3,<3.6` dependency
- `apis/ideas/get_ideas.py` — Motor async queries + cache integration
- `apis/projects/get_projects.py` — Motor async queries + cache integration
- `tests/conftest.py` — Motor safety-net fixture + cache cleanup
- `tests/apis/ideas/test_router.py` — AsyncMock for Motor
- `tests/apis/projects/test_router.py` — AsyncMock for Motor

### Results
- **2872 passed**, 0 failed (46.06s)

---

## Session — 2026-04-10 (v0.62.2)

**Focus**: API latency fix — GET /projects and GET /ideas taking 10+ seconds

### Root Causes Identified
1. **No MongoDB projection on workingIdeas** — full 50–200 KB documents transferred for list queries
2. **Missing `created_at` index** on `projectConfig` and standalone index on `workingIdeas`
3. **Sync pymongo calls blocking async event loop** — `count_documents()` and `find()` inside `async def`
4. **`count_documents({})` instead of `estimated_document_count()`** for unfiltered projects
5. **`VALID_PAGE_SIZES` missing 5 and 6** — web app requests returned 400

### Files Changed
- `apis/ideas/get_ideas.py` — exclusion projection, run_in_executor
- `apis/ideas/models.py` — IDEA_LIST_PROJECTION, VALID_PAGE_SIZES expanded
- `apis/projects/get_projects.py` — estimated_document_count, run_in_executor
- `apis/projects/models.py` — VALID_PAGE_SIZES expanded
- `scripts/setup_mongodb.py` — new `created_at DESC` indexes for projectConfig + workingIdeas
- `tests/apis/projects/test_router.py` — mock `estimated_document_count`

### User Feedback Created
- `obsidian/User Feedback/GAP-api-projects-ideas-slow-latency.md` — detailed analysis with 3 recommendations + 1 suggestion *(deleted after all tasks resolved in v0.63.0)*

### Results
- **2862 passed**, 0 failed (52.20s)

---

## Session — 2026-04-10 (v0.62.1)

**Focus**: Log error investigation, API latency analysis, and performance fixes

### Log Analysis Findings (crewai.log — April 10)
- **22 ERRORs, 18 WARNINGs** across 17,766 log lines (00:01–10:02)
- **15 Slack file upload failures** — `files_upload_v2` failing on transient errors with no retry
- **6 Jira issueLink 404s** — comma-separated issue keys (e.g. "CJT-1612,CJT-1613") passed as single value to Jira API
- **1 SSO introspection failure** — per-request `httpx.AsyncClient` creation overhead
- **1 CrewAI bus dead** — executor thread died, auto-reinitialised
- **No API latency middleware** — no visibility into request timing or slowness

### Fixes Applied
1. **Jira issue-link 404s** (`tools/jira/_tool.py`): Added `_split_issue_keys()` helper using regex `[A-Z][A-Z0-9]+-\d+` to extract individual Jira keys from comma-separated strings. Both `blocks_key` and `is_blocked_by_key` now iterate over extracted keys instead of passing raw string.
2. **Slack file upload retry** (`apis/slack/_slack_file_helper.py`): `upload_content_file()` now retries up to 2 times with linear backoff (1s, 2s) on transient failures. Error logging only fires after all attempts exhausted.
3. **API latency middleware** (`apis/__init__.py`): New `@app.middleware("http")` logs request duration, sets `X-Process-Time` response header, and logs WARNING for requests >2000ms.
4. **SSO client reuse** (`apis/sso_auth.py`): Replaced per-request `httpx.AsyncClient` context manager with a long-lived `_sso_http_client` singleton, eliminating TLS handshake/DNS overhead on every token validation.

### Test Results
- **2862 passed**, 0 failed, 13 warnings in 52.72s

---

## Session — 2026-04-09 (v0.62.0)

**Focus**: Implement TASK-idea-refinement-3-options and TASK-jira-kanban-board-style from User Feedback

### Changes
1. **Idea Refinement 3-Options** — Added `generate_alternatives_task` to idea refiner tasks.yaml. Modified `refine_idea()` to check for 3 trigger conditions (auto cycles complete, low confidence <3.0, direction change >40%) and generate 3 alternative directions. Interactive mode presents via Slack callback; autonomous auto-selects option 0. Return value changed to 3-tuple `(idea, history, options_history)`. New PRDState field `refinement_options_history`. New MongoDB `save_refinement_options()`. New Slack `idea_options_blocks()` builder. Fixed confidence threshold from 6.0→3.0 (1-5 scale).
2. **Jira Kanban Board Style** — Jira ticketing now reads `board_style` from projectConfig (defaults to "scrum"). Kanban uses flat 2-phase pipeline: skeleton → Tasks (no Epics/Stories/Sub-tasks hierarchy). New `build_jira_kanban_tasks_stage()`, `generate_kanban_skeleton_task`, `create_kanban_tasks_task`. Scrum-only phases auto-skip for kanban. Updated `build_jira_ticketing_stage` to route kanban vs scrum.
3. **Deleted 4 GAP files** — engineering-plan-tech-level, idea-refinement-options-frequency, jira-kanban-structure, webapp-monorepo-decision
4. **Deleted 2 TASK files** — TASK-idea-refinement-3-options.md, TASK-jira-kanban-board-style.md (implemented)

### Tests
- 11 new idea refiner options tests (score parsing, confidence, direction change, callback, auto-select)
- 19 new Jira kanban tests (board style, skeleton phase, epics skip, kanban tasks, ticketing routing)
- 4 MongoDB persistence tests, 7 Slack block builder tests
- All 2850+ tests passing

### Files Modified
- `agents/idea_refiner/agent.py` — 3-options logic, helper functions
- `agents/idea_refiner/config/tasks.yaml` — `generate_alternatives_task`
- `agents/orchestrator/config/tasks.yaml` — kanban skeleton + tasks config
- `orchestrator/_jira.py` — kanban routing, `_get_board_style()`, `build_jira_kanban_tasks_stage()`
- `orchestrator/__init__.py`, `orchestrator/stages.py` — new exports
- `flows/_constants.py` — `refinement_options_history`, updated `jira_phase` description
- `flows/prd_flow.py` — 3-tuple unpacking
- `mongodb/working_ideas/_sections.py` — `save_refinement_options()`
- `apis/slack/blocks/_idea_options_blocks.py` — Block Kit builder
- `version.py` — v0.62.0
- `obsidian/` — Changelog, Agents/Idea Refiner, Flows/Idea Refinement Flow, Flows/Jira Ticketing Flow, Orchestrator Overview, Module Map, Database/workingIdeas Schema

---

## Session — 2026-04-07 (v0.61.0)

**Focus**: Gap ticket resolution — implement user answers to 4 follow-up clarity tickets

### Changes
1. **Engineering Plan — Progressive Disclosure (Answer: C)** — Updated Engineering Manager task prompt (`agents/eng_manager/config/tasks.yaml`) to always use progressive disclosure format: high-level summary per section followed by Technical Deep-Dive sub-section with full detail + ASCII diagrams
2. **Jira Board Style — Schema (Answer: C)** — Added `board_style` field to `projectConfig` schema (default `"scrum"`, alternative `"kanban"`). Updated `create_project()` in repository with new parameter
3. **Webapp Monorepo — Decision Recorded (Answer: A)** — Keep separate repos (`c9s_idea_foundry_web`). No code changes needed
4. **Codex Task: Idea Refinement 3 Options** — Created `TASK-idea-refinement-3-options.md` for presenting 3 alternative directions at key decision points (after 3 auto cycles, on confidence drop below 6, on significant direction change)
5. **Codex Task: Jira Kanban Flow** — Created `TASK-jira-kanban-board-style.md` for implementing flat-task Kanban mode (3-phase vs 5-phase Scrum) gated by `board_style` project setting

### Gap Tickets Resolved
- `GAP-flow-engineering-plan-tech-level.md` — Deleted (implemented)
- `GAP-flow-idea-refinement-options-frequency.md` — Deleted (codex task created)
- `GAP-flow-jira-kanban-structure.md` — Deleted (schema done, codex task created)
- `GAP-webapp-monorepo-decision.md` — Deleted (decision recorded, no code needed)

### Files Modified
- `agents/eng_manager/config/tasks.yaml` — Progressive disclosure format
- `mongodb/project_config/repository.py` — `board_style` field + parameter
- `version.py` — v0.61.0
- `obsidian/Flows/Engineering Plan Flow.md` — Progressive disclosure docs
- `obsidian/Agents/Engineering Manager.md` — Updated expected output
- `obsidian/Database/projectConfig Schema.md` — `board_style` field
- `obsidian/Changelog/Version History.md` — v0.61.0 entry
- `obsidian/Sessions/Session Log.md` — This entry

---

## Session — 2026-04-04 (v0.59.2)

**Focus**: SSO bootstrap, deployment validation, and async fix

### Root Cause
The SSO app "Idea Foundry" was submitted as an app request but **never approved** — SSO server returns `AUTH_2009: Application has not been approved`. Additionally, zero SSO environment variables were configured in `.env`.

### Changes
1. **SSO .env configuration** — Added SSO_ENABLED, SSO_BASE_URL, SSO_CLIENT_ID, SSO_CLIENT_SECRET, SSO_JWT_PUBLIC_KEY_PATH, SSO_ISSUER, SSO_EXPECTED_APP_ID, SSO_WEBHOOK_SECRET to `.env`
2. **RSA public key** — Downloaded `sso_public_key.pem` from SSO server for local JWT verification
3. **sso_bootstrap.sh** — One-time script: admin login (with 2FA support), list/approve pending app requests, save credentials to `.env`, download public key, validate client_id
4. **dev_setup.sh** — Added section 8b: SSO health check, credential validation, client_id acceptance test for UAT/PROD. Added SSO_BASE_URL and SSO_CLIENT_ID to UAT/PROD required vars; SSO_CLIENT_SECRET and SSO_ENABLED to PROD required vars
5. **Async fix** — Converted `_introspect_remotely()` to async (same event-loop blocking pattern as v0.59.1). Updated 3 call sites in `sso/router.py` to `await`

### Files Modified
- `.env` — Added SSO configuration block
- `sso_public_key.pem` — RSA public key for JWT verification (new)
- `scripts/sso_bootstrap.sh` — SSO app bootstrap script (new)
- `scripts/dev_setup.sh` — SSO validation for UAT/PROD deployments
- `src/.../apis/sso_auth.py` — `_introspect_remotely()` → async
- `src/.../apis/sso/router.py` — 3 `_introspect_remotely()` calls → `await`
- `src/.../version.py` — v0.59.2 entry

### Tests: 2807 passed, 0 failed

---

## Session — 2026-04-06 (v0.59.3)

**Focus**: SSO bootstrap script fix — multi-environment redirect_uris and credential persistence

### Root Cause
The app "Idea Foundry" was registered (client_id: `2b5037b93bec30bcd2bfed5d24132ecc`) but the `client_secret` and `app_id` were not saved to `.env`. Since the client_secret is only shown once at registration, it was lost. The old script also required re-running for each environment (DEV/UAT/PROD) with different redirect_uris, generating new credentials each time.

### Changes
1. **Multi-environment redirect_uris** — Script now registers with ALL redirect_uris (DEV localhost, DEV ngrok, UAT, PROD) in a single registration. Same client_id/secret works across all environments.
2. **SSO_JWT_PUBLIC_KEY_PATH auto-update** — After downloading the RSA public key, the script now updates `SSO_JWT_PUBLIC_KEY_PATH=sso_public_key.pem` in `.env` (previously only saved the file but didn't update the env var).
3. **Webhook subscription** — Added step 7: registers webhook subscription via `POST /sso/webhooks/register` and saves `SSO_WEBHOOK_SECRET` to `.env`.
4. **Smart existing-app detection** — Checks if `SSO_CLIENT_SECRET` is already saved before prompting re-registration. If secret is missing, warns user that OAuth token exchange will fail and recommends re-registration.
5. **SSO_EXPECTED_APP_ID verification** — Added to verification checklist.
6. **Simplified deployment** — UAT/PROD now only needs `SERVER_ENV=UAT|PROD` in `.env` — no script re-run needed.

### Files Modified
- `scripts/sso_bootstrap.sh` — Complete rewrite of app registration and verification flow
- `src/.../version.py` — v0.59.3 entry

### Next Steps
- Run `./scripts/sso_bootstrap.sh` to delete the broken registration and create fresh credentials with all redirect_uris
- The script will prompt to delete the existing "Idea Foundry" app since client_secret is missing

---

## Session — 2026-04-06 (v0.57.0)

**Focus**: Review and clean up User Feedback gap tickets; implement agent transparency features

### Changes
1. **Agent activity messages** — New `agent_activity` progress events fired before every crew kickoff in:
   - `_executive_summary.py` (draft, critique, refine — 3 events)
   - `_section_loop.py` (critique, refine — 2 events per section)
   - `_ceo_eng_review.py` (CEO review, Engineering plan — 2 events)
   - `_ux_design.py` (Phase 1 draft, Phase 2 review — 2 events)
   - `_flow_handlers.py` — handler with agent-specific emojis (📝 PM, 🔍 Critic, 💼 CEO, 🛠️ Eng, 🎨 UX, 🧑‍🎨 Senior Designer)

2. **Requirements assumptions display** — After requirements breakdown completes, final evaluation posted to Slack via `requirements_assumptions` progress event, showing ambiguities/assumptions

3. **UX Design phase events** — `ux_design_draft_complete` and `ux_design_review_start` events now handled in Slack progress poster (previously fired but silently dropped)

4. **Gap ticket cleanup** — Deleted 9 resolved tickets (8 from v0.55.0 + AUDIT index). Updated 4 in-progress tickets with v0.57.0 implementation details

### Files Modified
- `src/.../flows/_executive_summary.py` — 3 `agent_activity` events
- `src/.../flows/_section_loop.py` — 2 `agent_activity` events
- `src/.../flows/_ceo_eng_review.py` — 2 `agent_activity` events
- `src/.../flows/_ux_design.py` — 2 `agent_activity` events
- `src/.../apis/slack/_flow_handlers.py` — handlers for `agent_activity`, `requirements_assumptions`, `ux_design_draft_complete`, `ux_design_review_start`
- `src/.../orchestrator/_requirements.py` — `requirements_assumptions` event in `_apply()`
- `src/.../version.py` — v0.57.0 CodexEntry

### Gap Tickets
- **Deleted (9)**: api-user-profile, api-ux-design, config-report-md-cleanup, docs-boilerplate-cr-cleanup, docs-readme-intent-sync, docs-readme-version-history, slack-iterate-idea-intent, webapp-design-decisions, AUDIT-flow-interactivity-plan
- **Updated (4)**: realtime-progress-streaming, executive-review-interactivity, ux-design-integration, engineering-plan-context
- **Remaining (11)**: 3 with unanswered follow-up questions, 4 pure future work, 4 partially implemented

### Tests
- **2419 passed**, 1 pre-existing failure (test_retry.py — rate limit backoff assertion)
- 243 targeted tests pass (flow + orchestrator + progress poster)

### Version
- `version.py`: CodexEntry for v0.57.0
- `Changelog/Version History.md`: v0.57.0 row added

---

## Session — 2026-04-05 (v0.56.0)

**Focus**: Implement flow audit gap ticket answers (10 tickets)

### Changes
1. **CEO Review approval gate** — Full plumbing across 8 files:
   - `prd_flow.py`: `ceo_review_approval_callback` field
   - `_ceo_eng_review.py`: approval gate after EPS generation (approve/reject/edit)
   - `_ceo_review_blocks.py` (NEW): Block Kit blocks with Approve/Skip buttons
   - `blocks/__init__.py`: export `ceo_review_blocks`
   - `_flow_handlers.py`: `resolve_ceo_review()`, `make_ceo_review_gate()`, `make_auto_ceo_review_gate()`, `ceo_review_awaiting_approval` progress event
   - `router.py`: wired CEO gate in `_run_slack_prd_flow()`, cleanup in finally block
   - `service.py`: `ceo_review_approval_callback` parameter on `run_prd_flow()` and `resume_prd_flow()`
   - `_dispatch.py`: `ceo_review_approve`/`ceo_review_reject` in `_KNOWN_ACTIONS`, ack labels, dispatch routing
   - `_callbacks.py`: `make_slack_ceo_review_callback()` factory
   - `_flow_runner.py`: wired CEO callback in interactive flow
   - `interactive_handlers/__init__.py`: export `make_slack_ceo_review_callback`

2. **Transparent critique** — `exec_summary_critique` progress event in `_executive_summary.py`, handled by progress poster to post Critic reasoning to Slack

3. **Pipeline step counter** — `orchestrator.py` passes `step`/`total_steps` to progress events, progress poster shows `[1/3]` tags

4. **Project config fields** — `design_preferences`, `review_checklists`, `technical_profile` dict/list fields added to `projectConfig` schema and `create_project()`

5. **Gap ticket updates** — All 10 flow audit tickets updated:
   - 3 marked `in-progress` with partial implementation (executive-review, realtime-progress, engineering-plan)
   - 3 marked `in-progress` with follow-up questions (idea-refinement Q3, jira-ticketing Q1, engineering-plan Q2)
   - 4 marked `in-progress` with user decisions recorded (section-drafting, confluence-publishing, journey-dashboard, prd-versioning)
   - 4 more marked `in-progress` with partial implementation (ux-design, jira-ticketing, idea-refinement)

### Tests
- All **2777 tests pass** (0 failures)

### Version
- `version.py`: appended CodexEntry for v0.56.0
- `Changelog/Version History.md`: added v0.56.0 row

## Session — 2026-04-04 (v0.55.0)

**Scope**: Implement all user-answered gap tickets
**Version**: v0.54.2 → v0.55.0

### Changes

- **Resolved 8 gap tickets**, 1 moved to in-progress:

  **New features (3):**
  1. `GET/PATCH /user/profile` — merged SSO identity + local preferences.
     New `userPreferences` MongoDB collection with `user_id` unique index.
     Fields: `display_name`, `default_project_id`, `timezone`,
     `notification_preferences`.
  2. `POST /flow/ux-design/{run_id}` — triggers UX design generation
     for completed PRDs. Returns 202, background task via existing
     `ux_design_flow.py`. Added `ux_design_status` and `ux_design_content`
     to `GET /flow/runs/{run_id}` response.
  3. `iterate_idea` — distinct Slack flow (list → pick → re-refine).
     New `BTN_ITERATE_IDEA` button, `cmd_iterate_idea` command handler,
     `handle_iterate_idea()` session handler, `idea_iterate_<N>`
     interaction dispatch. Separated iterate phrases from create_prd.

  **Documentation fixes (5):**
  4. README intent table: 12 → 20 intents synced with Slack Integration doc.
  5. README version history: updated from v0.9.4 to 15 recent significant
     versions (v0.25.0–v0.54.1) with link to full history.
  6. DESIGN.md Section 15: resolved all 8 design decisions per user answers
     (SSE, Milkdown, C9S SSO, sidebar dropdown, fixed columns, icons+text,
     both notifications, both dark mode). Added 10 Decisions Log entries.
  7. Boilerplate CR cleanup: removed example `- [ ]` items from 22
     obsidian pages across Database/, Flows/, APIs/.
  8. Deleted `report.md` from repo root (unrelated LLM research paper).

  **Analysis (1):**
  9. Web app screen gap analysis in GAP-webapp-frontend-framework.md:
     5 missing screen designs identified (Project Detail, Idea Detail,
     PRD Editor, Publishing, Activity Feed).

### New Files

- `src/.../mongodb/user_preferences/__init__.py`
- `src/.../mongodb/user_preferences/repository.py`
- `src/.../apis/user_profile/__init__.py`
- `src/.../apis/user_profile/router.py`
- `src/.../apis/prd/_route_ux_design.py`

### Testing

All existing tests passing. New endpoints follow established patterns.

---

## Session — 2026-04-03 (v0.54.2)

**Scope**: User Feedback — full gap audit and ticket creation
**Version**: v0.54.1 → v0.54.2

### Changes

- Performed full codebase audit across APIs, Slack, Database, Flows,
  Web App, README, source code TODOs, and environment variables.

- Created **9 gap tickets** in `obsidian/User Feedback/`:

  **Gaps requiring user input (5):**
  1. `GAP-api-user-profile-endpoint.md` — 5 design questions for `PATCH /user/profile`
  2. `GAP-api-ux-design-endpoint.md` — 4 design questions for `POST /flow/ux-design/{run_id}`
  3. `GAP-slack-iterate-idea-intent.md` — Is `iterate_idea` an alias or distinct flow?
  4. `GAP-webapp-frontend-framework.md` — Framework, hosting, priority, repo structure
  5. `GAP-webapp-design-decisions.md` — 8 unresolved DESIGN.md decisions (SSE, editor, auth, etc.)

  **Quick-win gaps (4, no user input needed):**
  6. `GAP-docs-readme-intent-sync.md` — README shows 12/20 intents
  7. `GAP-docs-boilerplate-cr-cleanup.md` — Template CRs polluting 15+ pages
  8. `GAP-docs-readme-version-history.md` — Version table stale at v0.9.4
  9. `GAP-config-report-md-cleanup.md` — Unrelated report.md at repo root

- Updated `_template.md` to include the agent-suggested answer format
  for user-facing questions.

- Each gap ticket includes agent-suggested answers prefilled for user review.

### Testing

No code changes — documentation only. Tests unaffected.

---

## Session — 2026-04-03 (v0.54.1)

**Scope**: User Feedback gap ticket system
**Version**: v0.54.0 → v0.54.1

### Changes

- Created `obsidian/User Feedback/_template.md` — structured gap ticket
  template with frontmatter (status, priority, domain, created), context,
  current/expected behaviour, affected area checklist, acceptance criteria,
  and resolution tracking sections.

- Updated `CODEX.md`:
  - Added `User Feedback/` to Obsidian Knowledge Base table
  - Added `Gap / missing feature found` to "When to Update Which Page" table
  - Added new **Gap Ticket Workflow** section with naming convention,
    priority/status values, and Codex processing instructions.

### Testing

No code changes — documentation only. Tests unaffected.

---

## Session — 2026-04-03 (v0.54.0)

**Scope**: Obsidian API docs cleanup — deprecate redundant summary files
**Version**: v0.53.0 → v0.54.0

### Changes

- **Deleted 7 summary files**: Health API.md, Ideas API.md, Projects
  API.md, PRD Flow API.md, Publishing API.md, SSO Webhooks API.md,
  Slack API.md — all superseded by per-route files in domain folders.

- **Migrated unique content**:
  - Status Lifecycle table + PRD Sections → Ideas/GET ideas-{run_id}.md
  - ExecutiveSummaryDraft, PRDDraftDetail, PRDSectionDetail schemas +
    ErrorResponse → PRD Flow/GET flow-runs-{run_id}.md
  - Web App Integration Flow + Agent Providers + PRD Sections Reference
    → PRD Flow/POST flow-prd-kickoff.md
  - PublishingErrorResponse schema → Publishing/POST publishing-confluence-{run_id}.md
  - Block Kit action ID tables (with descriptions) → Slack/POST slack-interactions.md
  - Thread State + Smart Thread Routing → Slack/POST slack-events.md
  - Webhook Delivery schema → Slack/POST slack-kickoff.md

- **Fixed 50+ stale wiki links** across Database schema pages:
  `[[PRD Flow API]]` → `[[PRD Flow/]]`, etc. for all 7 deleted files.

- **Updated CODEX.md** doc-update rules to reference per-route folders
  instead of deleted summary files.

- **Kept**: API Overview.md (master index), SSO API.md (sole docs for
  18 SSO endpoints, no per-route folder).

### Testing

No code changes — documentation only. Tests unaffected.

---

## Session — 2026-04-03 (v0.53.0)

**Scope**: API per-route restructuring for agent-friendly updates
**Version**: v0.52.0 → v0.53.0

### Changes

- **Health API**: Split `apis/health/router.py` (313 lines, 5 endpoints)
  into per-route files: `get_health.py`, `get_version.py`,
  `get_slack_token.py`, `post_slack_token_exchange.py`,
  `post_slack_token_refresh.py`. Router.py now assembles sub-routers.

- **Ideas API**: Split `apis/ideas/router.py` (255 lines, 3 endpoints)
  into per-route files: `get_ideas.py`, `get_idea.py`,
  `patch_idea_status.py`. Shared models extracted to `models.py`.

- **Projects API**: Split `apis/projects/router.py` (300 lines, 5 endpoints)
  into per-route files: `get_projects.py`, `get_project.py`,
  `post_project.py`, `patch_project.py`, `delete_project.py`.
  Shared models extracted to `models.py`.

- **SSO Webhooks**: Moved top-level `apis/sso_webhooks.py` into
  `apis/sso_webhooks/` package with `router.py` and `post_events.py`.

- **Obsidian docs**: Updated 14 per-route API docs to point to new
  source files. Updated Module Map with all new files.

### Not Changed (Already Well-Structured)

- **Publishing** (9 endpoints): Thin router delegates to `service.py` — no split needed.
- **PRD Flow** (10 endpoints): Already split into `router.py` + `_route_actions.py` + `service.py`.
- **Slack** (highly modular): 3 routers + 23 handler files — gold standard.
- **SSO** (18 endpoints): All thin httpx proxies — no DB logic to separate.
- **Integrations** (1 endpoint): Too small to split further.

### Test Results

- 1115 API tests passing (0 failures)

---

## Session — 2026-04-02 (v0.52.0)

**Scope**: SSO authentication router — full C9S Single Sign-On integration
**Version**: v0.51.0 → v0.52.0

### Changes

- **New SSO router**: Created `apis/sso/` package with 18 `/auth/sso/*`
  endpoints mirroring the Executive Assistant SSO API:
  - OAuth2 redirect login (`GET /auth/sso/login`)
  - Direct email/password login (`POST /auth/sso/login`)
  - 2FA verification (`POST /auth/sso/login/verify-2fa`)
  - Google Sign-In (`POST /auth/sso/google`)
  - Registration: redirect, direct, verify-2fa, resend-2fa
  - OAuth2 callback (`GET /auth/sso/callback`)
  - Status check, userinfo (Bearer required)
  - Password reset + confirm
  - Token refresh
  - Re-authentication + 2FA (Bearer required)
  - Logout + logout-all (Bearer required)
- **Tests**: 29 new tests in `tests/apis/sso/test_sso_router.py`
- **Resolves**: 404 on `POST /auth/sso/login` (endpoint didn't exist)
- **Docs**: New `obsidian/APIs/SSO API.md`, updated API Overview,
  Module Map, Environment Variables, Version History, .env.example

---

## Session — 2026-04-02 (v0.51.0)

**Scope**: Obsidian vault restructure — docs-only release
**Version**: v0.50.0 → v0.51.0

### Changes

- **Changelog restructure**: Rewrote `Version History.md` from per-version
  sections into 7 weekly groupings with 3-column tables (Version, Date,
  Summary). Added `> [!info]` callout for version scheme.
- **YAML frontmatter**: Added frontmatter (tags, aliases) to all 103 markdown
  files following Obsidian property conventions. Tags derived from folder
  hierarchy (e.g. APIs→`api, endpoints`, Agents→`agents, crewai`).
- **6 API docs completed**: Added Database Algorithm sections to 2 Publishing
  and 4 Slack per-route files with accurate logic traced from source code
  (`apis/publishing/router.py`, `apis/slack/router.py`).
- **7 old API files deprecated**: Added `> [!warning] Deprecated` callouts to
  monolithic API files (Health, Projects, Ideas, PRD Flow, Publishing, Slack,
  SSO Webhooks) pointing to per-route replacements.
- **Home.md updated**: Version to 0.51.0, added APIs navigation section with
  per-route folder links, `> [!tip] Making Changes` callout for Change
  Requests workflow, expanded vault tree.
- **Obsidian best practices**: Applied callouts (tip, warning, info, note),
  wikilinks, consistent formatting throughout vault.

### Stats

- No Python source changes — docs-only release
- No new tests required
- 2746 tests still passing

---

## Session — 2026-04-01 (v0.50.0)

**Scope**: Activity Log & Integration Status APIs, obsidian/APIs restructure
**Version**: v0.49.0 → v0.50.0

### Changes

- **GET /flow/runs/{run_id}/activity**: New endpoint returning agent interaction
  events from `agentInteraction` collection. Configurable `limit` (1–500,
  default 50). Models: `ActivityEvent`, `ActivityLogResponse` in `_responses.py`.
- **GET /integrations/status**: New endpoint returning Confluence/Jira connection
  status based on env vars. URL masking for security. New `apis/integrations/`
  router package registered in `apis/__init__.py`.
- **Obsidian restructure**: Split 8 monolithic API docs into 32 individual
  per-route files across 8 subdirectories (Health, Projects, Ideas, PRD Flow,
  Publishing, Slack, SSO Webhooks, Integrations). Each file has clear
  request/response schemas and database algorithms. Updated `API Overview.md`
  with full endpoint index (39 endpoints, 11 routers).
- **[CHANGE] docs**: Created `[CHANGE] POST flow-ux-design-{run_id}.md` and
  `[CHANGE] PATCH user-profile.md` for 2 low-confidence APIs needing user input.
- **Tests**: 5 activity log tests + 4 integrations tests (9 new). 2746 passing.

---

## Session — 2026-03-31 (v0.48.0)

**Scope**: Fix CrewAI event-bus shutdown corruption — all PRD flows crashing
**Version**: v0.47.2 → v0.48.0

### Problem
Every PRD flow since March 26 was crashing with `cannot schedule new futures after shutdown` at the Executive Summary stage (or earlier, during idea refinement). 15 failures on March 30 alone. Zero successful flow completions.

### Root Cause
CrewAI’s `crewai_event_bus` singleton (in `crewai/events/event_bus.py`) registers `atexit.register(crewai_event_bus.shutdown)` at module import time. The `shutdown()` method permanently kills the internal `ThreadPoolExecutor` (`_sync_executor.shutdown(wait=True)`) and sets `_shutting_down = True`. Once the atexit handler fires (triggered by server restart signals, process fork, or any exit path), the singleton is permanently dead — there is no recovery mechanism in CrewAI. All subsequent `crew.kickoff()` calls crash when the event bus tries to `_sync_executor.submit(...)`.

The singleton is a `__new__`-based singleton that only calls `_initialize()` on first creation. After `shutdown()`, there is no mechanism to reinitialise.

### Changes
1. **`scripts/crewai_bus_fix.py`** (NEW) — Three functions:
   - `_is_executor_alive(bus)` — checks if `_sync_executor._shutdown` is False
   - `ensure_crewai_event_bus()` — detects dead bus and calls `bus._initialize()` to create fresh executor + event loop thread; thread-safe with double-check locking
   - `install_crewai_bus_fix()` — calls `atexit.unregister(bus.shutdown)` to prevent future corruption, then `ensure_crewai_event_bus()` to repair any existing damage
2. **`apis/__init__.py`** — Step 0c in lifespan: calls `install_crewai_bus_fix()` at server startup, before any flow resumption
3. **`apis/prd/service.py`** — `run_prd_flow()` and `resume_prd_flow()` both call `ensure_crewai_event_bus()` before creating the flow
4. **`scripts/retry.py`** — `crew_kickoff_with_retry()` calls `ensure_crewai_event_bus()` before the retry loop (defense-in-depth)
5. **Tests**: 9 new tests in `test_crewai_bus_fix.py` covering executor alive/dead detection, reinitialisation after shutdown flag, reinitialisation after dead executor, idempotency, atexit unregistration

### Key Lesson
CrewAI’s `atexit.register(crewai_event_bus.shutdown)` is fundamentally incompatible with long-running server processes that may receive restart signals. The singleton pattern with no reinitialisation path makes this a permanent poison. The fix works around it by: (a) unregistering the atexit handler, and (b) calling `_initialize()` directly when corruption is detected.

---

## Session — 2026-03-30 (v0.47.2)

**Scope**: Thread session isolation — reject non-owner replies in Slack threads
**Version**: v0.47.1 → v0.47.2

### Problem
When an admin was configuring a project in a Slack thread (setup wizard, memory entry, interactive run, or exec feedback), another user posting in that thread (e.g. "nice") would be processed by the LLM intent classifier instead of being ignored. The system only enforced thread ownership for pending-create sessions.

### Root Cause
`_handle_thread_message_inner()` had three missing user-ownership checks:
1. **Interactive runs lookup** (lines 305-312): Matched on `(channel, thread_ts)` only — the `"user"` field was stored in `_interactive_runs` but never checked.
2. **Exec feedback lookup** (lines 342-344): Same pattern — `_pending_exec_feedback` stored `"user"` but only matched on `(channel, thread_ts)`.
3. **Fallthrough to `_interpret_and_act`**: No guard checked if another user owned a setup wizard or memory entry session in the thread.

### Changes
1. **`apis/slack/_event_handlers.py`** — Interactive-run lookup now checks `info.get("user") == user`. Non-owner silently ignored.
2. **`apis/slack/_event_handlers.py`** — Exec-feedback lookup now checks `info.get("user") == user`. Non-owner silently ignored.
3. **`apis/slack/_event_handlers.py`** — Final guard before `_interpret_and_act` calls `get_thread_owner()` and rejects non-owners.
4. **`apis/slack/session_manager.py`** — New `get_thread_owner(channel, thread_ts)` checks all pending states (creates, setup wizard, memory entries) and returns the owning user.
5. **Tests**: 12 new tests in `TestGetThreadOwner`, `TestThreadOwnerGuard`, `TestInteractiveRunIsolation`. Fixed existing `test_thread_reply_sends_feedback` to use matching user.

### Key Lesson
Thread session ownership must be enforced at every routing point, not just the first pending-create check. The `user` field was already stored in all in-memory state dictionaries but was never validated during message routing.

---

## Session — 2026-03-30 (v0.47.1)

**Scope**: Fix Confluence published checkmarks in Slack product list
**Version**: v0.47.0 → v0.47.1

### Problem
After a one-time reset script cleared `confluence_published` in `productRequirements` delivery records, the Slack product list still showed `:white_check_mark: Confluence PRD Page` checkmarks and "View Confluence" buttons for ideas that were not actually published. The "Publish Confluence" button was missing for these ideas.

### Root Cause
`_doc_to_product_dict()` in `_queries.py` used `or base["confluence_url"]` to infer `confluence_published=True`. The reset script cleared the delivery record but left stale `confluence_url` fields on `workingIdeas` documents. Same pattern existed in `_startup_delivery.py` where `confluence_done` was derived from `doc.get("confluence_url")`.

### Changes
1. **`mongodb/working_ideas/_queries.py`** — `_doc_to_product_dict()`: `confluence_published` now derives ONLY from `delivery.confluence_published`. Stale URL on workingIdeas doc no longer implies published. Also flipped URL source priority: delivery record first, workingIdeas doc as display-only fallback.
2. **`orchestrator/_startup_delivery.py`** — `confluence_done` check: Removed `or bool(doc.get("confluence_url"))` fallback. Only delivery record authority.
3. **Tests**: 5 new regression tests in `TestDocToProductDict` (stale URL not published, URL from delivery only, no record no URL, stale URL no record). Updated 2 existing startup delivery tests to use delivery record authority.
4. **`scripts/clear_stale_confluence_urls.py`** — One-time cleanup script to `$unset` stale `confluence_url` from `workingIdeas` where delivery record doesn't confirm publication.
5. **Fixed v0.47.0 CODEX entry**: date was a string instead of `date()` object.

### Key Lesson
When resetting data with one-time scripts, ALL collections that hold related fields must be updated — not just the "primary" record. The enrichment logic merged data from two collections and the reset script only cleaned one.

---

## Session — 2026-03-30 (v0.47.0)

**Scope**: Background Slack token refresh scheduler
**Version**: v0.46.1 → v0.47.0

### Problem
Slack rotating tokens (`xoxe.*`) expire every 12 hours and refresh tokens are **single-use**. The token manager only refreshed lazily (on demand when `get_valid_token()` was called). If the server was down during the refresh window — e.g. overnight — both the access token AND the refresh token expired permanently (`invalid_refresh_token`), bricking the bot until manual re-installation via OAuth.

Timeline from logs: Last successful refresh at 12:48 Mar 29 (12h TTL → 00:48 Mar 30). Server went down after 23:26 Mar 29. Token expired at 00:48 Mar 30 with no server running. First startup attempt at 12:01 Mar 30 → refresh token permanently dead.

### Root Cause
1. **No proactive refresh**: Token rotation was purely reactive — only triggered when a Slack API call happened and the token was about to expire
2. **Token manager returned dead tokens**: On `invalid_refresh_token`, `get_valid_token()` fell through to step 4 and returned the expired token instead of None
3. **No circuit breaker**: Event handlers processed messages even with a dead token, wasting LLM credits on responses that could never be delivered

### Changes
1. **`tools/token_refresh_scheduler.py`** (NEW) — Background daemon thread that:
   - Runs every 30 minutes (configurable via `TOKEN_REFRESH_INTERVAL_SECONDS`)
   - Refreshes tokens when < 1 hour remaining (configurable via `TOKEN_REFRESH_BUFFER_SECONDS`)
   - Runs an immediate refresh sweep on startup (catches tokens that expired while server was down)
   - Supports disable via `TOKEN_REFRESH_SCHEDULER_ENABLED=false`
   - Follows the same pattern as `publishing/scheduler.py` (daemon thread + stop event)

2. **`apis/__init__.py`** — Integrated scheduler into server lifespan:
   - Step 7b: `start_token_refresh_scheduler()` on startup
   - Shutdown hook: `stop_token_refresh_scheduler()`

3. **`tools/slack_token_manager.py`** — `get_valid_token()` fix:
   - `invalid_refresh_token` → tries `SLACK_BOT_TOKEN` env var fallback → returns `None` (not expired token)
   - Generic refresh failures still fall through to step 4 (backward compat for transient errors)

4. **`apis/slack/_event_handlers.py`** — Circuit breakers:
   - `_handle_app_mention()`: checks `_get_slack_client()` first, returns early if None
   - `_handle_thread_message()`: same circuit breaker

5. **Tests**:
   - `test_token_refresh_scheduler.py` — 12 tests (start/stop lifecycle, refresh logic, multi-team, integration)
   - `test_dm_and_pending_routing.py` — autouse fixture now patches `_get_slack_client` for circuit breaker compat
   - 2699 tests passing

### Key Lesson
**Detection ≠ Resolution.** The v0.46.1 fix only improved logging/detection of the expired token — it logged ERROR messages but still returned the dead token and processed every message. The actual fix needed to: (a) stop returning dead tokens, (b) prevent processing when no token, and (c) proactively prevent token death via background refresh.

---

## Session — 2026-03-30 (v0.46.0)

**Scope**: Enhanced knowledge base for CrewAI agents
**Version**: v0.45.1 → v0.46.0

### Problem
The knowledge folder had only 3 files (user_preference, project_architecture, prd_guidelines) — insufficient domain-specific context for the 16+ agent roles. Agents lacked detailed scoring criteria, domain expertise frameworks, engineering standards, and UX design standards that could improve output quality through CrewAI's knowledge/RAG system.

### Changes
1. **Created 5 new knowledge files** in `knowledge/`:
   - `idea_refinement.txt` — Domain identification framework, hard questions (user/market, problem/solution, competitive/strategic, technical/feasibility, business model), refinement output standards, common pitfalls
   - `engineering_standards.txt` — 9-section engineering plan structure, architecture decision principles, technology stack defaults, staff engineer review checklist (N+1 queries, race conditions, trust boundaries, etc.), Jira ticket quality standards, engineering quality gates
   - `review_criteria.txt` — Unified scoring criteria for all pipeline stages: idea refinement (5 criteria, 1-5 scale), executive summary (7 criteria, 1-10 scale), PRD sections (6 criteria, 1-10 scale), requirements breakdown (6 criteria, 1-5 scale), CEO review expectations, UX 7-pass review methodology, QA review quality gates
   - `ux_design_standards.txt` — 12-section design spec structure, atomic design principles, design token architecture, 6 interaction states per element, 5 page states, WCAG 2.1 AA accessibility, responsive breakpoints, AI slop blacklist (10 anti-patterns), typography/color/component standards, CSS token export format
   - `agent_roles_and_workflow.txt` — Full 19-agent roster across 5 functional areas, pipeline execution order (Phase 0-5), LLM model tier assignments, engagement manager orchestration strategy, idea agent capabilities, agent tool assignments, interactive Slack flow, cross-agent data flow diagram

2. **Updated `knowledge_sources.py`** — Added 5 new builder functions, added `review_criteria.txt` to `build_prd_knowledge_sources()` (now returns 4 sources), registered new file path constants

3. **Wired knowledge to agents**:
   - Idea Refiner: added `idea_refinement.txt` for domain expertise during refinement cycles
   - Staff Engineer: added `engineering_standards.txt` for production safety audits
   - QA Lead: added `review_criteria.txt` for test methodology review
   - QA Engineer: added `review_criteria.txt` for edge case and security testing

4. **Updated `project_architecture.txt`** — Expanded knowledge file listing (3→8 files), expanded agent roster from 5 to 19 with full role descriptions organized by functional area

5. **Updated tests** — Fixed `test_returns_three_sources` → `test_returns_four_sources`, updated ordering test for 4th source

### Result
- 2653 tests passing in 55.81s
- Knowledge base expanded from 3 files to 8 files
- All new knowledge files based on actual agent YAML configs and task definitions

---

## Session — 2026-03-30 (v0.45.1)

**Scope**: Fix test suite latency — 7.6x speedup
**Version**: v0.45.0 → v0.45.1

### Problem
Full test suite took 596s (9m 55s). Three PRD flow tests each took 130-154s because `_trigger_ux_design_flow` was not mocked, causing real LLM API calls during finalization. Three Slack interaction tracking tests took ~11s each due to unmocked engagement manager hitting real Gemini API. Two HTTP error tests had real `time.sleep` during retry backoff.

### Changes

- `tests/flows/test_prd_flow.py` — Added `@patch("...._finalization._trigger_ux_design_flow")` to 3 tests: `test_callback_true_continues_to_sections`, `test_skip_phase1_when_exec_summary_has_enough_iterations`, `test_phase1_runs_when_below_threshold`
- `tests/apis/slack/test_interaction_tracking.py` — Added `_handle_engagement_manager` and `find_idea_by_thread` mocks to all 4 `_call_with_intent` helpers. Split `test_with_session_reaches_intent_handler[unknown]` into separate `test_with_session_unknown_reaches_engagement_manager` test
- `tests/tools/test_gemini_chat.py` — Added `time.sleep` mock to `test_interpret_http_error`
- `tests/tools/test_openai_chat.py` — Added `time.sleep` mock to `test_interpret_http_error`

### Test Results
2653 passed in 78.65s (was 595.77s)

---

## Session — 2026-03-29 (v0.45.0)

**Scope**: Complete Figma removal — UX design now produces markdown-only specifications
**Version**: v0.44.0 → v0.45.0

### Problem
UX design flow was tightly coupled to Figma Make integration (Playwright browser automation, OAuth, REST API). The `tools/figma/` package added complexity, environmental dependencies (Playwright, Chromium), and fragile external service coupling. UX design should produce pure markdown specifications without external tool dependencies.

### Changes

**Source code (30+ files)**:
- Deleted entire `tools/figma/` directory (6 files: `_config.py`, `_api.py`, `_client.py`, `figma_make_tool.py`, `login.py`, `__init__.py`)
- Removed `FigmaMakeTool` from UX Designer agent (`tools=[]`)
- Renamed state fields: `figma_design_prompt` → `ux_design_content`, `figma_design_status` → `ux_design_status`, removed `figma_design_url`
- Removed `figma_api_key`/`figma_team_id` from project config API models, MongoDB `create_project()`, and Slack setup wizard (5→3 steps)
- Removed Figma-specific statuses (`"prompting"`, `"prompt_ready"`)
- Updated all MongoDB query/status functions with backward-compatible fallback reads
- Updated CLI state restoration, project knowledge builder, flow handlers, Slack blocks
- Rewrote UX Designer agent config: role → "Design Specification Specialist", task → `generate_ux_design_spec_task`
- Updated Engagement Manager agent config references

**Tests (10 files)**:
- Deleted `tests/tools/test_figma_tool.py`
- Updated 9 test files across `tests/apis/`, `tests/flows/`, `tests/` root
- Fixed syntax error in `_requirements.py` (escaped quotes from prior edit)
- All 2653 tests passing

**Obsidian documentation (15+ files)**:
- `Agents/UX Designer.md` — Rewrote role, goal, backstory, tools, task sections
- `APIs/Projects API.md` — Removed all Figma fields from schemas/examples
- `APIs/Ideas API.md` — Replaced `figma_design_url`/`figma_design_status` with `ux_design_status`
- `Flows/UX Design Flow.md` — Updated state fields, skip conditions, data flow
- `Flows/PRD Flow.md` — Updated state field table
- `Flows/Jira Ticketing Flow.md` — `figma_design_url` → `ux_design_content`
- `Flows/Requirements Breakdown Flow.md` — Updated skip condition field name
- `Flows/Engineering Plan Flow.md` — "Figma design" → "UX design"
- `Architecture/Environment Variables.md` — Removed entire Figma section (5 env vars)
- `Architecture/Module Map.md` — Removed `figma/` entry
- `Architecture/Project Overview.md` — Removed Figma from project config description
- `Architecture/Coding Standards.md` — Updated logging example
- `Database/projectConfig Schema.md` — Removed 5 Figma fields from schema
- `Database/workingIdeas Schema.md` — Renamed to UX Design section with backward compat note
- `Tools/Tools Overview.md` — Moved Figma to Removed Tools section
- `Agents/Agent Roles.md` — Updated UX Designer description
- `Agents/Engagement Manager.md` — Removed Figma from publication list
- `Changelog/Version History.md` — Added v0.45.0 entry

### Test Results
2653 passed, 61 warnings in 947.84s

---

## Session — 2026-03-29 (v0.44.0)

**Scope**: PRD Flow Obsidian docs breakdown — individual flow step pages with detailed step-by-step documentation
**Version**: v0.43.9 → v0.44.0

### Problem
The monolithic PRD Flow page packed all 10 pipeline phases into a single document without step-by-step detail on skip conditions, approval gates, scoring criteria, function signatures, data flow, or resume behaviour. Users could not edit individual flow steps, and Codex could not efficiently diff flow changes.

### Changes

Created 10 new Obsidian pages under `obsidian/Flows/`:
1. **Idea Refinement Flow.md** — 4 steps (skip check, refinement execution, state update, approval gate), 5 scoring criteria, progress events, resume logic
2. **Executive Summary Flow.md** — 6 steps (pre-draft gate, parallel drafting, critique scoring, user feedback gate, refinement loop, completion gate), 7 critique criteria
3. **Requirements Breakdown Flow.md** — 4 steps (skip check, execution, state update, approval gate), 6 scoring criteria, auto-approve conditions
4. **CEO Review Flow.md** — 4 steps (skip check, agent execution, output processing, persistence), reasoning mode, challenge areas
5. **Engineering Plan Flow.md** — 4 steps + user decision gate, 9 coverage areas, data flow diagram
6. **Section Drafting Flow.md** — 7 steps per section (skip, parallel draft, persistence, approval, critique, refinement, degenerate detection), 6 critique criteria, 12-section table
7. **Finalization Flow.md** — 10 steps (assemble, UX appendix, write file, persist, XHTML, mark complete, knowledge sync, state flags, trigger UX, trigger post-completion)
8. **UX Design Flow.md** — 2 phases (draft with 5 steps, review with 3 steps), 12-section spec coverage, 7-pass review table, trigger conditions
9. **Confluence Publishing Flow.md** — 5 steps (skip check, config resolve, publish, state update, delivery record), startup auto-publish
10. **Jira Ticketing Flow.md** — 5 phases (skeleton → Epics/Stories → Sub-tasks → Review → QA Test), phase state machine diagram, approval gate invariant, 23 regression tests

Updated `obsidian/Flows/PRD Flow.md`:
- Converted to index page with pipeline overview table
- ASCII execution flow diagram with approval gates marked
- Links to all 10 sub-pages via `[[wikilinks]]`

Updated `CODEX.md`:
- "When to Update Which Page" table references individual flow pages
- "Documentation Updates" table adds flow step/approval gate triggers

Updated `version.py`:
- Appended v0.44.0 CodexEntry (Y bump — new feature set)

---

## Session — 2026-03-29 (v0.43.9)

**Scope**: Agent Roles Obsidian docs breakdown — individual agent pages with full role, goal, backstory, tasks
**Version**: v0.43.8 → v0.43.9

### Problem
The monolithic Agent Roles page had brief summaries without the exact YAML role/goal/backstory text, task definitions, or scoring criteria. Users could not edit individual agent configurations, and Codex could not efficiently diff agent changes against the documentation.

### Changes

Created 12 new Obsidian pages under `obsidian/Agents/`:
1. **Idea Refiner.md** — Research tier, 2 tasks (refine_idea, evaluate_quality), 5 scoring criteria (all ≥ 3), 3-10 iteration cycles
2. **Product Manager.md** — Research/Critic tiers, 3 tasks (draft_prd, critique_prd, draft_section), Gemini/OpenAI/Critic variants, FileReadTool + DirectoryReadTool
3. **Requirements Breakdown.md** — Research tier, 2 tasks (breakdown_requirements, evaluate_requirements), 6 scoring criteria (all ≥ 4)
4. **Orchestrator.md** — Research tier, 2 tasks (publish_to_confluence, generate_jira_skeleton), ConfluencePublishTool + JiraCreateIssueTool, 3 agent variants
5. **CEO Reviewer.md** — Research tier, 1 task (generate_executive_product_summary), reasoning=True, Phase 1.5a
6. **Engineering Manager.md** — Research tier, 1 task (generate_engineering_plan), Architecture/Data/Test/Security/Deployment coverage, Phase 1.5b
7. **Staff Engineer.md** — Research tier, 1 task (create_staff_engineer_review_subtasks), JiraCreateIssueTool, 11-point audit checklist, Jira Phase 4a
8. **QA Lead.md** — Research tier, 1 task (create_qa_lead_review_subtasks), JiraCreateIssueTool, 9-point verification checklist, Jira Phase 4b
9. **QA Engineer.md** — Research tier, 1 task (create_qa_engineer_test_subtasks), JiraCreateIssueTool, edge/security/rendering tests, Jira Phase 5
10. **UX Designer.md** — Research tier, 1 task (generate_figma_make_prompt), FigmaMakeTool, 3 agent variants (UX Designer, Design Partner, Senior Designer), 2-phase flow
11. **Engagement Manager.md** — Basic tier, 4 tasks (engagement_response, idea_to_prd_orchestration, heartbeat_update, user_steering_detection), fast path, 6 key functions
12. **Idea Agent.md** — Basic tier, 1 task (idea_query), fast path, context extraction, steering recommendations, gap analysis, 4 key functions

Updated `obsidian/Agents/Agent Roles.md`:
- Converted from monolithic reference to index page
- 4 category tables (PRD Pipeline, Jira Review, Design, Conversational agents)
- ASCII execution order diagram
- Links to all 12 sub-pages via `[[wikilinks]]`

Updated `CODEX.md`:
- "When to Update Which Page" table now references individual agent pages
- "Documentation Updates" table adds agent role/goal/backstory/task triggers

Updated `version.py`:
- Appended v0.43.9 CodexEntry

Updated `/memories/codex-rules.md`:
- Added per-agent page list to documentation update rules

---

## Session — 2026-03-29 (v0.43.8)

**Scope**: MongoDB Schema Obsidian docs breakdown — individual collection pages with field-level schemas
**Version**: v0.43.7 → v0.43.8

### Problem
The monolithic MongoDB Schema page lacked field-level detail and API references. Users could not edit individual collection schemas, and Codex could not efficiently diff and apply changes.

### Changes

Created 9 new Obsidian pages under `obsidian/Database/`:
1. **crewJobs Schema.md** — 16 fields, status flow, timing fields, 11 repository functions
2. **workingIdeas Schema.md** — 25+ fields across 7 categories (core, timestamps, Slack, exec summary, requirements, sections, output, Jira, Figma), 30+ repository functions
3. **productRequirements Schema.md** — 11 fields, Jira ticket record sub-schema, delivery status lifecycle
4. **projectConfig Schema.md** — 14 fields, Figma OAuth fields, Slack file refs sub-schema
5. **projectMemory Schema.md** — 6 fields, memory entry formats for 3 categories (idea_iteration, knowledge, tools)
6. **agentInteraction Schema.md** — 17 fields, predicted next step sub-schema, 8 repository functions
7. **userSession Schema.md** — dual schema (user sessions vs channel sessions), 9 repository functions
8. **slackOAuth Schema.md** — 12 fields, token rotation support, 6 repository functions
9. **userSuggestions Schema.md** — 11 fields, suggestion type enum, 2 repository functions

Updated `obsidian/Database/MongoDB Schema.md`:
- Converted from monolithic reference to index page
- Links to all 9 sub-pages via `[[wikilinks]]`
- Added collection relationship diagram
- Added key relationships table with cardinality

### Tests
- No code changes — documentation only
- 2728 tests passing (unchanged)

---

## Session — 2026-03-29 (v0.43.7)

**Scope**: API Obsidian docs breakdown — individual domain pages with field-level schemas
**Version**: v0.43.6 → v0.43.7

### Problem
The monolithic API Overview page was too large for targeted edits. Users could not edit individual API domain schemas, and Codex could not efficiently diff and apply changes.

### Changes

Created 7 new Obsidian pages under `obsidian/APIs/`:
1. **Health API.md** — 5 endpoints, response schemas for health probe, version, Slack token management
2. **Projects API.md** — 5 CRUD endpoints, `ProjectCreate`/`ProjectUpdate`/`ProjectItem`/`ProjectListResponse` with full field tables (types, constraints, defaults, descriptions)
3. **Ideas API.md** — 3 endpoints, `IdeaItem`/`IdeaListResponse`/`IdeaStatusUpdate`, status lifecycle, PRD sections reference table
4. **PRD Flow API.md** — 9 endpoints, 19 models documented (all request/response/domain/nested schemas), web app integration flow, agent providers, error codes
5. **Publishing API.md** — 9 endpoints, `PendingPRDItem`/`ConfluencePublishResult`/`JiraCreateResult`/`DeliveryStatusResponse`/`WatcherStatusResponse` with field-level docs
6. **Slack API.md** — 5 endpoints, `SlackPRDKickoffRequest`/`SlackPRDKickoffResponse`, events API (dedup, thread state, smart routing), Block Kit interactions (17 command actions, flow control, publishing, session)
7. **SSO Webhooks API.md** — 1 endpoint, HMAC auth, 6 supported event types with data field tables

Updated `obsidian/APIs/API Overview.md`:
- Converted from monolithic reference to index page
- Links to all 7 sub-pages via `[[wikilinks]]`
- Retains auth, CORS, pagination, error handling reference
- Router mounting table now links to sub-pages

### Tests
- No code changes — documentation only
- 2728 tests passing (unchanged)

---

## Session — 2026-03-29 (v0.43.6)

**Scope**: API and Obsidian documentation update for web app integration
**Version**: v0.43.5 → v0.43.6

### Problem
API documentation and Obsidian knowledge base were incomplete for web app frontend integration. Missing: Projects, Ideas, and SSO Webhook path specs in OpenAPI; no web app integration guide; outdated server lifecycle steps; no security scheme definitions; CORS not documented.

### Changes

**OpenAPI spec** (`docs/openapi/openapi.json`):
1. Updated title to "Idea Foundry API" (was "CrewAI Product Feature Planner API")
2. Rewrote description as web app integration guide covering auth, pagination, error handling, CORS, status lifecycle, and typical polling flow
3. Added 7 new path files: `projects/list.json`, `projects/{project_id}.json`, `ideas/list.json`, `ideas/{run_id}.json`, `ideas/{run_id}_status.json`, `sso/webhooks_events.json`
4. Added 10 new component schemas: `ProjectCreate`, `ProjectUpdate`, `ProjectItem`, `ProjectListResponse`, `IdeaItem`, `IdeaListResponse`, `IdeaStatusUpdate`
5. Added security schemes: `ssoAuth` (JWT Bearer), `slackVerification` (HMAC), `ssoWebhook` (HMAC)
6. Added API tags for Swagger UI organization
7. Updated version to 0.43.6

**Obsidian pages**:
1. `APIs/API Overview.md` — Complete rewrite as web app integration reference with auth guide, CORS, pagination, error handling, full endpoint tables with request/response models, status lifecycle diagram, router mounting table
2. `Architecture/Project Overview.md` — Added dual-client architecture table (Web App + Slack Bot), API surface summary for web app
3. `Architecture/Server Lifecycle.md` — Updated to current startup sequence (2a archive stale, 2b resumable partition, 8b auto-resume), added CORS configuration section
4. `Architecture/Environment Variables.md` — Reorganized with web app integration section first (CORS_ALLOWED_ORIGINS, SSO vars), removed duplicate SSO section
5. `Database/MongoDB Schema.md` — Added web app data model mapping table (collection → API endpoints → purpose)

### Result
All API documentation now covers the full endpoint surface (40+ endpoints across 10 routers) with typed schemas, security definitions, and integration guides suitable for a frontend developer building a web app. 2728 tests passing.

---

## Session — 2026-03-28 (v0.43.5)

**Scope**: Fix 47-second server startup regression
**Version**: v0.43.4 → v0.43.5

### Problem
Server startup went from ~3-5s yesterday to ~47-50s today. The entire delay occurred in the `startup_markdown_review` pipeline stage's `_should_skip()` function with zero log output during the 47-second gap.

### Root Causes
1. **Heavy import chain via credential checks**: `_helpers.py`'s `_has_confluence_credentials()` and `_has_jira_credentials()` lazily imported from `tools.confluence_tool` / `tools.jira_tool`. This triggered `tools/__init__.py` which eagerly imports `file_read_tool` → `from crewai_tools import FileReadTool` → full CrewAI framework (~15s).
2. **Full document fetch from Atlas**: `find_completed_without_confluence()` fetched entire documents (avg ~100KB each, containing embedded iterations and sections) for all 11 completed ideas from MongoDB Atlas. 85 docs, 8.4MB total — the full-doc query took ~47s over the network even though only run_id fields were needed for filtering.

### Changes
1. **`orchestrator/_helpers.py`**: Inlined `_has_confluence_credentials()` and `_has_jira_credentials()` as direct env-var checks. Removed lazy imports from `tools` package entirely. Credentials checked: `ATLASSIAN_BASE_URL`, `ATLASSIAN_USERNAME`, `ATLASSIAN_API_TOKEN` (+ `JIRA_PROJECT_KEY` for Jira).
2. **`mongodb/working_ideas/_queries.py`**: Rewrote `find_completed_without_confluence()` as a three-phase query: (1) lightweight projection to get run_ids only (0.05s), (2) filter out already-published IDs, (3) fetch full docs only for unpublished run_ids (0 docs in common case).
3. **Updated tests**: `tests/mongodb/working_ideas/test_repository.py` — adapted `TestFindCompletedWithoutConfluence` mocks for two-phase query pattern.

### Result
Startup pipeline stage: **~47s → ~0.9s** (51x speedup). All 2728 tests passing.

---

## Session — 2026-03-28 (v0.43.4)

**Scope**: Fix thread-history mention gate
**Version**: v0.43.3 → v0.43.4

### Problem
Bot stopped responding to thread follow-ups after server restarts. User sent "list of ideas" in an existing thread without @mentioning the bot → message silently ignored.

### Root Cause
The `has_bot_thread_history()` check in `events_router.py` was gated behind `_bot_mentioned`. After a server restart, the in-memory thread cache was empty, so the only way to recognize the thread was via the MongoDB `agentInteractions` lookup — but that lookup was skipped because the user didn't @mention the bot.

### Solution
Removed the `_bot_mentioned` gate from the `has_thread_history` check. If the bot has already replied in a thread (per MongoDB), the thread is an established conversation — no @mention required. This matches the existing `has_flow_thread` fallback which was already ungated.

### Files Changed
- `src/.../apis/slack/events_router.py` — removed `if _bot_mentioned:` gate from `has_thread_history` check
- `tests/apis/slack/test_dm_and_pending_routing.py` — updated `TestMentionGateThreadHistory` to assert dispatch without @mention

---

## Session — 2026-03-28 (v0.43.3)

**Scope**: Engagement Manager & Idea Agent latency optimization
**Version**: v0.43.2 → v0.43.3

### Problem
Engagement Manager and Idea Agent responses took 3-5 seconds due to CrewAI `Crew.kickoff()` framework overhead (~2-4 s) — even though the underlying Gemini Flash model call only takes ~200-500 ms.

### Root Cause
CrewAI's `Crew.kickoff()` adds overhead for agent construction, task creation, tool registration, and telemetry. The conversational agents (Engagement Manager, Idea Agent) don't need this machinery — they're simple prompt-in/text-out tasks.

### Solution
1. New `generate_chat_response()` in `tools/gemini_chat.py` — direct Gemini REST API call for plain-text responses (same `urllib.request` pattern as `interpret_message()`). `thinkingBudget=0`, 30s timeout, 2 retries.
2. `handle_unknown_intent()` now uses fast path by default. Falls back to CrewAI on failure or when `ENGAGEMENT_MANAGER_USE_CREWAI=true`.
3. `detect_user_steering()` same fast/fallback pattern (also controlled by `ENGAGEMENT_MANAGER_USE_CREWAI`).
4. `handle_idea_query()` same fast/fallback pattern (controlled by `IDEA_AGENT_USE_CREWAI=true`).
5. 21 new tests covering fast path, fallback behavior, and `generate_chat_response()`.
6. 2728 tests passing.

### Files Changed
- `src/.../tools/gemini_chat.py` — added `generate_chat_response()`
- `src/.../agents/engagement_manager/agent.py` — split into fast/crewai paths
- `src/.../agents/idea_agent/agent.py` — split into fast/crewai paths
- `tests/tools/test_gemini_chat.py` — 8 new tests
- `tests/agents/test_engagement_manager.py` — 9 new tests
- `tests/agents/test_idea_agent.py` — 6 new tests

---

## Session — 2026-03-28 (v0.43.2)

**Scope**: Immediate "Thinking…" acknowledgment on all Slack interactions
**Version**: v0.43.1 → v0.43.2

### Problem
When users sent messages or clicked buttons, there was no immediate feedback — the bot was silently processing (LLM classification, handler dispatch) for several seconds before any response appeared.

### Solution
1. New `_post_thinking()` in `_message_handler.py` — posts `:thinking_face: <@user> Thinking…` via best-effort `chat_postMessage`. Never raises.
2. `interpret_and_act()` calls `_post_thinking()` before `_interpret_and_act_inner()` — covers all @mention + thread-reply paths that reach the LLM.
3. `cmd_*` button clicks in `_dispatch.py` now post a "Thinking…" ack via `_post_ack()` (same pattern as project-session button acks).
4. Thread replies routed to pending-state handlers, feedback queues, and setup wizards are unaffected — those respond instantly.

### Files Modified
- `src/.../apis/slack/_message_handler.py` — added `_post_thinking()`, wired into `interpret_and_act()`
- `src/.../apis/slack/interactions_router/_dispatch.py` — added "Thinking…" ack for cmd_* buttons

### Tests
- 2707 tests passing (no new tests needed — defensive `_post_thinking` exits silently in test env)

---

## Session — 2026-03-27 (v0.43.1)

**Scope**: Reduce Slack iteration noise; enhance section/exec-summary completion messages with content summary + file fallback
**Version**: v0.43.0 → v0.43.1

### Problem
During PRD generation, every section iteration and executive summary iteration posted a message to the Slack thread — flooding the thread with per-iteration refinement noise. Completion messages also lacked content summaries and didn't tag the user.

### Solution
1. **Suppressed iteration noise** — `section_iteration` and `exec_summary_iteration` events in `make_progress_poster()` now pass silently (no Slack messages). Only `section_start` and completion events are shown.
2. **Enhanced completion messages** — `section_complete` and `executive_summary_complete` now:
   - Tag the user (`<@user>`) when a user ID is available (interactive flows)
   - Include the full section content as an inline preview
   - If content exceeds Slack's 2800-char block limit, truncate with hint and upload full content as a downloadable `.md` file via `files_upload_v2`
3. **Content in event details** — `prd_flow.py` and `_executive_summary.py` now include `content` in the `section_complete` and `executive_summary_complete` event detail dicts.

### Files Modified
- `src/.../apis/slack/_flow_handlers.py` — suppress iteration events, enhance completion events with tag/summary/file fallback
- `src/.../flows/prd_flow.py` — add `content` to `section_complete` event details (both emission sites)
- `src/.../flows/_executive_summary.py` — add `content` to `executive_summary_complete` event details (both emission sites)
- `tests/.../test_progress_poster.py` — updated suppression test, added 12 new tests
- `tests/.../test_automated_flow.py` — updated 3 tests for suppression behavior

### Tests
- 2707 total tests passing (2696 → 2707, net +11)
- 12 new tests in `test_progress_poster.py` (suppression, user tag, content summary, file fallback)
- 3 updated tests in `test_automated_flow.py` (iteration suppression)

---

## Session — 2026-03-27 (v0.43.0)

**Scope**: New Idea Agent for in-thread iteration queries + v0.42.4 security audit completion
**Version**: v0.42.3 → v0.42.4 → v0.43.0

### Problem
When users asked questions like "what is the current summary?" during an active idea iteration thread, the Engagement Manager responded with generic navigation help instead of specific iteration data. Users couldn't get information about the current state of their idea, refined text, sections, or critiques during active flows.

### Solution — Idea Agent (v0.43.0)
New `agents/idea_agent/` module with:
- **agent.yaml** — "Idea Analyst & Iteration Advisor" role with backstory covering real-time situational awareness
- **tasks.yaml** — `idea_query_task` for information requests, steering feedback, and gap analysis
- **agent.py** — `create_idea_agent()`, `handle_idea_query()`, `extract_steering_feedback()`, `_extract_iteration_context()`
- **_extract_iteration_context()** — builds structured context from working-idea MongoDB document (status, refined idea, refinement history, exec summary, requirements, engineering plan, sections, critiques)
- **Steering** — when users provide direction feedback, the agent produces structured recommendations persisted to `agentInteraction` for downstream agents
- **_handle_idea_agent()** in `_message_handler.py` — posts response and handles steering persistence
- **Engagement Manager disengaged** — during active flows (inprogress/paused), both `general_question` and unknown intents route to the Idea Agent instead of the Engagement Manager

### Security Audit Completion (v0.42.4)
All HIGH and MEDIUM findings from ISO 27001 audit fixed and tested:
- XSS, SSRF, figma_api_key exposure, error detail leakage, input validation, Slack verify warning, path traversal, injection guards, auth on health endpoints, query limit bounds

### Tests
- 21 new Idea Agent tests
- 2696 total tests passing (up from 2675)

### Files Created
- `src/.../agents/idea_agent/__init__.py`
- `src/.../agents/idea_agent/agent.py`
- `src/.../agents/idea_agent/config/agent.yaml`
- `src/.../agents/idea_agent/config/tasks.yaml`
- `tests/agents/test_idea_agent.py`

### Files Modified
- `src/.../apis/slack/_message_handler.py` — added `_handle_idea_agent()`, rewired `general_question` and unknown intent dispatch
- `tests/apis/slack/test_flow_thread_routing.py` — updated summary integration test for Idea Agent routing
- `src/.../version.py` — v0.42.4 + v0.43.0 entries
- `obsidian/Agents/Agent Roles.md` — Idea Agent entry + Engagement Manager disengagement note
- `obsidian/Architecture/Module Map.md` — idea_agent/ entry
- `obsidian/Changelog/Version History.md` — v0.42.4 + v0.43.0
- `obsidian/Sessions/Session Log.md` — this entry

---

## Session — 2026-03-27 (v0.42.3)

**Scope**: Root-cause fix — save_iteration() resurrecting archived ideas
**Version**: v0.42.2 → v0.42.3

### Problem
CrewAI flows kept running for archived ideas even after v0.42.2 cancel mechanism fixes. The flow for `d64725f5e861` was auto-resumed on every server restart despite being "archived".

### Root Cause (the real bug)
`save_iteration()` in `_sections.py` unconditionally set `status: "inprogress"` via `$set` on every section save. This meant:
1. User archives idea → MongoDB status = "archived"
2. Flow thread still running (cancel signal takes time to reach)
3. Next `save_iteration()` call → MongoDB status overwritten to "inprogress"
4. Server restart → `find_resumable_on_startup()` finds it as "inprogress" → auto-resumes
5. Cycle repeats infinitely

### Fixes
1. **`save_iteration()`** — checks current MongoDB status before writing; terminal statuses (archived, completed, failed) are never overwritten
2. **`save_executive_summary_iteration()`** — same guard
3. **`save_pipeline_step()`** — same guard
4. **`resume_prd_flow()`** — queries MongoDB and refuses to resume archived/failed runs
5. **`generate_sections()`** — early `check_cancelled()` before any pipeline work
6. **MongoDB fix** — manually archived `d64725f5e861` (was stuck as inprogress)

### Files Changed
- `src/.../mongodb/working_ideas/_sections.py` — 3 functions guarded against terminal status overwrite
- `src/.../apis/prd/service.py` — archive guard in resume_prd_flow
- `src/.../flows/prd_flow.py` — early cancellation check

### Tests
2675 passing (0 failing, 1 flaky unrelated test)

---

## Session — 2026-03-27 (v0.42.2)

**Scope**: Fix archive cancellation for resumed/auto-resumed flows
**Version**: v0.42.1 → v0.42.2

### Problem
Server was still running CrewAI flows for archived ideas. The v0.42.1 cancel mechanism only worked for flows started via `kick_off_prd_flow()` (Slack interactive start). Resumed flows (auto-resume on startup, manual resume) and the REST API archive path were missing critical cancel plumbing.

### Root Causes
1. `resume_prd_flow()` did not register a `cancel_event` — `request_cancel()` found nothing to set
2. `resume_prd_flow()` did not catch `FlowCancelled` — cancelled flows got paused instead of archived
3. `_run_slack_resume_flow()` (startup auto-resume) never registered cancel events
4. REST API `PATCH /ideas/{run_id}/status` archive path only called `mark_archived()` — no cancel signal, no gate unblocking, no crew job archival
5. `request_cancel()` silently did nothing when no event existed for the run_id

### Fixes
1. `resume_prd_flow()` — registers `cancel_events[run_id]`, catches `FlowCancelled`, cleans up in finally
2. `_run_slack_resume_flow()` — registers cancel event before calling resume
3. `request_cancel()` — creates + sets event if missing (defensive, archive always works)
4. REST API archive — calls `request_cancel()`, `_unblock_gates_for_cancel()`, `update_job_status("archived")`
5. `_resume_flow_background()` — checks MongoDB status before resuming, skips archived ideas
6. Fixed `completed_at` None validation error crashing GET /ideas

### Files Changed
- `src/.../apis/prd/service.py` — FlowCancelled handling + cancel_events registration in resume_prd_flow
- `src/.../apis/shared.py` — request_cancel creates event if missing
- `src/.../apis/slack/router.py` — cancel event registration in _run_slack_resume_flow
- `src/.../apis/ideas/router.py` — archive path now cancels flows + completed_at fix
- `src/.../apis/__init__.py` — _resume_flow_background checks archived status
- `tests/.../test_archive_cancel.py` — updated tests for new request_cancel behavior

### Tests
2675 passing (0 failing)

---

## Session — 2026-03-27 (v0.42.1)

**Scope**: Archive stops active flows — cooperative cancellation + scan cleanup
**Version**: v0.42.0 → v0.42.1

### Work Done
1. **FlowCancelled exception + cancel registry** — Added `FlowCancelled` exception and `cancel_events: dict[str, threading.Event]` registry to `shared.py`. Helper functions: `request_cancel()`, `is_cancelled()`, `check_cancelled()`.

2. **kick_off_prd_flow cancel event** — Creates `threading.Event()` and stores in `cancel_events[run_id]` before starting the daemon thread.

3. **execute_archive_idea signals cancel** — Calls `request_cancel(run_id)` and `_unblock_gates_for_cancel(run_id)` before archiving DB records.

4. **_unblock_gates_for_cancel** — New helper that sets all pending gate events for a run_id: exec_feedback, exec_completion, requirements_approval, and approval_events (interactive mode). Unblocked threads flow through to the next `check_cancelled()` checkpoint.

5. **PRDFlow cancellation checkpoints** — Added `check_cancelled(run_id)` at 6 strategic points in `generate_sections()`: after pipeline, before exec summary, before requirements, before CEO review, before eng plan, before each Phase 2 section.

6. **run_prd_flow FlowCancelled handler** — Catches `FlowCancelled`, sets `FAILED` status with "CANCELLED" error, job status "archived". Cleanup in finally block pops `cancel_events`.

7. **Interactive flow runner + router** — `_flow_runner.py` catches `FlowCancelled` with same status handling. Router suppresses error message for cancelled flows.

8. **get_run_documents() archived filter** — Changed from `$ne "completed"` to `$nin ["completed", "archived"]` so archived docs are not returned by resume/restart lookups.

9. **archive_stale_jobs_on_startup()** — New startup step in crew_jobs/repository.py. Cross-references non-final crew jobs against workingIdeas collection; archives jobs whose ideas have `status: "archived"`. Called in `apis/__init__.py` lifespan step 2a.

10. **Stale flow cleanup** — Cleaned up `d64725f5e861` ("new idea") which was stuck `inprogress` and auto-resumed every server restart (command-phrase guard issue from v0.42.0).

### Tests
- 17 new tests in `test_archive_cancel.py`
- 8 test classes: TestCancelRegistry, TestUnblockGates, TestArchiveSignalsCancel, TestRunPrdFlowCancelled, TestKickOffRegistersCancel, TestArchiveCancelsWaitingFlow, TestGetRunDocumentsArchived, TestArchiveStaleJobsOnStartup
- Updated `test_repository.py` assertion for `get_run_documents` query change
- Integration test verifies a flow thread waiting on a gate is unblocked and receives FlowCancelled

---

## Session — 2026-03-26 (v0.42.0)

**Scope**: Summarize ideas, user suggestions, admin config guard, archive knowledge file
**Version**: v0.41.0 → v0.42.0

### Work Done
1. **Summarize ideas intent** — New `summarize_ideas` intent with `_SUMMARIZE_IDEAS_PHRASES` added before `list_ideas` in priority order. `_handle_summarize_ideas()` uses Engagement Manager for AI-powered narrative summary. `BTN_SUMMARIZE_IDEAS` + `cmd_summarize_ideas` dispatch.

2. **User suggestions collection** — New `userSuggestions` MongoDB collection with `log_suggestion()` and `find_suggestions_by_project()`. Tracks `clarification_needed` (when Engagement Manager prefixes response with `[CLARIFICATION]`) and `unknown_intent` (when agent fails entirely).

3. **Engagement Manager category D** — `tasks.yaml` updated with category D "clarification needed" for ambiguous intents. Agent asked to prefix with `[CLARIFICATION]` so system can track.

4. **Admin-only config button** — `product_list_blocks()` now accepts `is_admin` kwarg; Config button hidden for non-admin users. `_handle_product_config()` adds `can_manage_memory()` guard. Callers in `_session_ideas.py` and `_session_products.py` pass admin status.

5. **Command-phrase idea guard** — New `_is_command_phrase_idea()` in `_message_handler.py` prevents auto-starting PRD flow when LLM extracts command phrases ("new idea", "add new idea", "create a prd") as the idea text. Prompts user for real idea instead.

6. **Archive moves knowledge file** — `archive_idea_knowledge()` in `project_knowledge.py` moves `projects/{name}/ideas/{title}.md` → `projects/{name}/archives/{YYYY}/{MM}/{DD}/{title}.md`. Called from `execute_archive_idea()`. Project overview page refreshed after move.

### Tests
- 22 new tests in `test_v042_fixes.py`
- Existing test updated: `test_product_list.py` (is_admin=True), `test_command_handler.py` (CMD_ACTIONS count 17), `test_setup_mongodb.py` (userSuggestions in EXPECTED)

---

## Session — 2026-03-26 (v0.41.0)

**Scope**: UX Design Flow Refactor — Standalone 2-Phase Post-PRD Flow
**Version**: v0.40.0 → v0.41.0

### Work Done
1. **Phase 1.5c removed from PRD flow** — `_run_ux_design` method deleted from PRDFlow; UX design import and Phase 1.5c block removed from `generate_sections()`. UX design is now a standalone post-PRD flow.

2. **_ux_design.py fully rewritten** — New 2-phase architecture:
   - `run_ux_design_draft()` — Phase 1: UX Designer + Design Partner collaborate on initial design spec
   - `run_ux_design_review()` — Phase 2: Senior Designer applies 7-pass review and produces final spec
   - `run_ux_design_flow()` — Orchestrates both phases
   - `_write_design_file()` — Fixed-name file writer (overwrites existing, no timestamp proliferation)
   - `_resolve_output_dir()` — Project-aware output directory resolution
   - `run_ux_design()` — Legacy backward-compat entry point

3. **File proliferation fix** — Changed from timestamped filenames (`ux_design_YYYYMMDD_HHMMSS.md`, 30+ files) to 2 fixed files: `ux_design_draft.md` and `ux_design_final.md`

4. **3 new YAML configs** — `design_partner.yaml` (gstack design-consultation, AI slop blacklist), `senior_designer.yaml` (gstack plan-design-review, 7-pass scoring), `ux_design_flow_tasks.yaml` (2 task definitions with 12-section spec + review criteria)

5. **3 new agent factories** — `create_design_partner()`, `create_senior_designer()`, `get_ux_design_flow_task_configs()` in `agent.py`, all with proper credential checks

6. **Standalone flow entry point** — `ux_design_flow.py` with `kick_off_ux_design_flow()`

7. **Finalization trigger** — `_trigger_ux_design_flow()` in `_finalization.py` with skip guards (no EPS, already completed/prompt_ready) and error propagation (BillingError/ModelBusyError/ShutdownError)

8. **Test suite rewritten** — 37 tests across 13 classes in `test_ux_design.py`; 3 test_prd_flow.py patches updated to remove `_run_ux_design` references

### Files Created
- `agents/ux_designer/config/design_partner.yaml`
- `agents/ux_designer/config/senior_designer.yaml`
- `agents/ux_designer/config/ux_design_flow_tasks.yaml`
- `flows/ux_design_flow.py`

### Files Modified
- `agents/ux_designer/agent.py` — 3 new factories + credential checks
- `agents/ux_designer/__init__.py` — exports updated
- `flows/_ux_design.py` — full rewrite (2-phase architecture)
- `flows/_finalization.py` — _trigger_ux_design_flow() added
- `flows/prd_flow.py` — Phase 1.5c removed
- `flows/__init__.py` — kick_off_ux_design_flow export
- `tests/flows/test_ux_design.py` — rewritten (37 tests)
- `tests/flows/test_prd_flow.py` — _mock_ux patches removed
- `version.py` — v0.41.0 CodexEntry

### Tests
- 37 UX design tests (13 classes)
- 2636 total tests passing

---

## Session — 2026-03-25 (v0.40.0)

**Scope**: Engagement Manager Project Knowledge Awareness
**Version**: v0.39.0 → v0.40.0

### Work Done
1. **_build_project_tools()** — New function in agent.py builds FileReadTool + DirectoryReadTool scoped to a project's knowledge folder (`src/projects/{name}/`). Loads completed-ideas context from MongoDB via `load_completed_ideas_context()`. Returns `(tools, ideas_context)` tuple; graceful fallback on DB/filesystem errors.

2. **create_engagement_manager(project_id)** — Now accepts optional `project_id`. When provided, agent receives file-reading tools and ideas context is appended to backstory, enabling holistic project knowledge queries.

3. **handle_unknown_intent(project_id)** — Now accepts optional `project_id`, builds `{project_knowledge}` template variable from completed ideas, passes to task description.

4. **engagement_response_task rewrite** — Task now classifies user messages into: (A) Knowledge question — summarize/compare ideas, detect duplication/synergies using file tools; (B) Action intent — recommend button clicks; (C) Idea feedback/steering. New `{project_knowledge}` template variable.

5. **agent.yaml backstory update** — Added "Project Knowledge & Idea Awareness" section describing file-reading capabilities, idea comparison, and duplication detection.

6. **_message_handler.py** — `handle_unknown_intent()` call now passes `project_id=session_project_id`.

### Files Modified
- `src/.../agents/engagement_manager/agent.py` — new `_build_project_tools()`, updated `create_engagement_manager()` + `handle_unknown_intent()`
- `src/.../agents/engagement_manager/config/tasks.yaml` — engagement_response_task rewritten
- `src/.../agents/engagement_manager/config/agent.yaml` — backstory expanded
- `src/.../apis/slack/_message_handler.py` — project_id passthrough
- `src/.../version.py` — v0.40.0 CodexEntry
- `tests/agents/test_engagement_manager.py` — 12 new tests (59 total)
- `obsidian/Sessions/Session Log.md` — v0.40.0 entry
- `obsidian/Changelog/Version History.md` — v0.40.0 entry

### Tests
- 59 engagement manager tests passing (12 new: 4 _build_project_tools, 3 create with project, 4 handle_unknown_intent with project, 1 YAML placeholder)
- 2614 total tests passing

---

## Session — 2026-03-24 (v0.39.0)

**Scope**: Engagement Manager PRD Orchestrator — Heartbeats, Steering, Session Isolation
**Version**: v0.38.0 → v0.39.0

### Work Done
1. **agent.yaml rewrite** — Expanded role to "Engagement Manager, PRD Orchestrator & Navigation Guide". Full backstory with agent team knowledge, 2-step orchestration strategy (Step 1 sequential: Idea Refinement → Exec Summary; Step 2 parallel/coordinated: remaining agents), heartbeat protocol, user steering detection, session isolation.

2. **3 new tasks in tasks.yaml** — `idea_to_prd_orchestration_task` (full lifecycle orchestration plan with template variables for idea, user, run, phase, history, steering), `heartbeat_update_task` (emoji-prefixed status updates), `user_steering_detection_task` (IGNORE/STEERING/QUESTION/FEEDBACK/UNRELATED classification with session isolation fast-path).

3. **5 new functions in agent.py** — `generate_heartbeat()` (template-based instant heartbeats, no LLM), `make_heartbeat_progress_callback()` (wraps PRD flow progress events into user-friendly messages via _PROGRESS_EVENT_MAP), `detect_user_steering()` (LLM-powered classification with fast-path session isolation for non-initiator messages), `_parse_steering_result()` (JSON/keyword parser), `orchestrate_idea_to_prd()` (wraps run_prd_flow with heartbeat callbacks and session isolation).

4. **.gitignore** — Changed `output/prds/` to `output/` to ignore entire output folder.

5. **conftest.py fix** — Raised recursion limit to 5000 for crewai 1.9.x + starlette/pydantic compatibility (model_rebuild exceeds default 1000 limit).

### Files Modified
- `.gitignore` — output/ folder fully ignored
- `src/.../agents/engagement_manager/config/agent.yaml` — complete rewrite
- `src/.../agents/engagement_manager/config/tasks.yaml` — 3 new tasks added
- `src/.../agents/engagement_manager/agent.py` — 5 new functions, expanded imports
- `src/.../agents/engagement_manager/__init__.py` — 4 new exports
- `src/.../version.py` — v0.39.0 CodexEntry
- `tests/conftest.py` — recursion limit fix
- `tests/agents/test_engagement_manager.py` — 32 new tests (47 total)
- `obsidian/Changelog/Version History.md` — v0.39.0 entry
- `obsidian/Agents/Agent Roles.md` — expanded Engagement Manager section
- `obsidian/Architecture/Module Map.md` — updated engagement_manager description

### Tests
- 47 engagement manager tests passing (32 new: 3 YAML config, 7 heartbeat, 4 progress callback, 3 steering detection, 4 steering parser, 6 orchestration, 2 progress event map + 15 existing)

---

## Session — 2026-03-24 (v0.38.0)

**Scope**: Publication Safety Overhaul — User-Triggered Publishing Only
**Version**: v0.37.1 → v0.38.0

### Work Done
1. **Duplicate Confluence fix** — `publish_to_confluence()` now accepts `page_id` parameter; when stored `confluence_page_id` exists in delivery record, page is updated by ID instead of creating duplicates. Added `_get_page_by_id()` to `confluence_tool.py`. Orchestrator `_confluence.py` and publishing service pass stored page_id.

2. **Auto-publish removal** — `_run_auto_post_completion()` gutted to log + notify only (no crew kickoff). `_run_phased_post_completion()` requires Confluence already published before starting Jira. Startup functions (`_cli_startup`, `components/startup`) now discovery-only. File watcher disabled. `build_startup_markdown_review_stage()` always skips.

3. **Confluence prerequisite for Jira** — All Jira creation paths (`_delivery_action_handler`, `_product_list_handler`, `_flow_handlers`) check for `confluence_url` before allowing Jira. User guided to publish Confluence first with interactive button. Removed `require_confluence=False` overrides.

### Files Modified
- `src/.../tools/confluence_tool.py` — added `_get_page_by_id()`, `page_id` param to `publish_to_confluence()`
- `src/.../orchestrator/_confluence.py` — pass stored page_id for updates
- `src/.../apis/publishing/service.py` — pass stored page_id in `publish_confluence_single/all()`
- `src/.../flows/_finalization.py` — gutted auto-publish, Confluence prerequisite in phased
- `src/.../orchestrator/_startup_review.py` — always-skip discovery-only
- `src/.../components/startup.py` — discovery-only
- `src/.../_cli_startup.py` — discovery-only
- `src/.../apis/publishing/watcher.py` — disabled
- `src/.../apis/slack/_flow_handlers.py` — Confluence-only publish, Jira button after
- `src/.../apis/slack/interactions_router/_delivery_action_handler.py` — Confluence prerequisite check
- `src/.../apis/slack/interactions_router/_product_list_handler.py` — Confluence prerequisite check
- `tests/` — 23 tests updated across 5 test files

### Test Results
- 2571 passed, 0 failed

---

## Session 001 — 2026-03-08

**Scope**: Obsidian Knowledge Base Setup
**Version**: v0.15.4 → (no version change — documentation only)

### Work Done
- Created Obsidian vault at `c9-prd-planner/C9 Product Ideas Planner`
- Populated 18 knowledge pages covering:
  - Architecture (Project Overview, Module Map, Server Lifecycle, Environment Variables, Coding Standards)
  - Agents (Agent Roles, LLM Model Tiers)
  - APIs (API Overview)
  - Changelog (Version History — full v0.1.0 to v0.15.4)
  - Database (MongoDB Schema)
  - Flows (PRD Flow)
  - Integrations (Slack, Confluence, Jira)
  - Knowledge (PRD Guidelines, User Preferences)
  - Orchestrator (Orchestrator Overview)
  - Testing (Testing Guide)
  - Tools (Tools Overview)
- Updated CODEX.md with Obsidian Knowledge Management section
- Added session/iteration update requirements to coding standards

### Key Decisions
- Vault path: `/Users/c9admin/Library/Mobile Documents/iCloud~md~obsidian/Documents/c9-prd-planner/C9 Product Ideas Planner`
- Used Obsidian `[[wikilinks]]` for inter-note navigation
- Session entries stored in `Sessions/Session Log.md`
- Template provided at `Templates/Session Entry.md`

### Files Modified
- `CODEX.md` — Added Obsidian Knowledge Management section
- 18 new Obsidian vault files created

---

<!-- Append new sessions below this line -->

## Session 002 — 2026-03-08

**Scope**: LLM 500 Error Handling + CODEX Knowledge Update
**Version**: v0.15.4 → v0.15.5

### Work Done
- Reviewed `crewai.log` for LLM errors — no actual HTTP 500s found, but discovered inadequate error handling
- `retry.py`: Added `_SERVER_ERROR_PATTERNS` for 500/502/504 classification with proper retry + backoff
- `gemini_chat.py`: Increased retries 2→3, added exponential backoff, non-retryable 4xx fail immediately
- `openai_chat.py`: Added retry logic (was zero retries), 3 attempts with backoff, retryable status codes
- Added 11 new tests across `test_retry.py`, `test_gemini_chat.py`, `test_openai_chat.py`
- Updated CODEX.md session-end checklist to require CrewAI knowledge source updates

### Files Modified
- `src/.../scripts/retry.py` — Server error patterns, retry classification
- `src/.../tools/gemini_chat.py` — Retry with backoff
- `src/.../tools/openai_chat.py` — Retry from scratch
- `tests/test_retry.py` — 5 server error tests
- `tests/tools/test_gemini_chat.py` — 3 retry tests
- `tests/tools/test_openai_chat.py` — 3 retry tests
- `CODEX.md` — Knowledge update requirement

---

## Session 003 — 2026-03-09

**Scope**: Fix Shutdown Error Handling
**Version**: v0.15.5 → v0.15.6

### Work Done
- Reviewed `crewai.log` — found "cannot schedule new futures after shutdown" errors causing 60+ seconds of wasted retries after server shutdown
- `retry.py`: Added `ShutdownError` class and `_SHUTDOWN_PATTERNS` — detected immediately with zero retries
- `_section_loop.py`: `ShutdownError` now re-raises instead of force-approving sections with incomplete content
- `service.py`: `ShutdownError` caught in both `run_prd_flow` and `resume_prd_flow` — pauses flow for auto-resume
- `apis/__init__.py`: Global exception handler returns HTTP 503 for `ShutdownError`
- Added 5 new tests to `tests/test_retry.py`

### Key Decisions
- Shutdown detection placed BEFORE model-busy check in retry loop to catch it earliest
- ShutdownError is a subclass of LLMError (same hierarchy as BillingError, ModelBusyError)
- Flows pause on shutdown rather than fail — enables auto-resume on next server start

### Files Modified
- `src/.../scripts/retry.py` — ShutdownError, _SHUTDOWN_PATTERNS
- `src/.../flows/_section_loop.py` — Re-raise ShutdownError
- `src/.../apis/prd/service.py` — Catch ShutdownError in both flow functions
- `src/.../apis/__init__.py` — Global 503 handler for ShutdownError
- `tests/test_retry.py` — 5 shutdown tests
- `src/.../version.py` — v0.15.6

---

## Session 004 — 2026-03-09

**Scope**: Critical Jira Approval Gate Regression Fix
**Version**: v0.15.7 → v0.15.8

### Problem
A prior fix (v0.15.7, Confluence slowness) added `confluence_only` param
to `build_post_completion_crew()` but failed to propagate it to ALL
callers. Five distinct code paths could create Jira tickets without user
approval:
1. `_run_auto_post_completion()` — called `build_post_completion_crew(flow)` without `confluence_only=True`
2. `build_startup_delivery_crew()` — had no `confluence_only` parameter at all
3. CLI startup (`_cli_startup.py`) — called startup crew without `confluence_only`
4. Server startup (`components/startup.py`) — called startup crew without `confluence_only`
5. `execute_restart_prd()` — called `kick_off_prd_flow()` without `interactive=True`, falling to auto-approve path

### Fixes Applied
1. `_finalization.py`: `_run_auto_post_completion()` → `confluence_only=True`
2. `_startup_delivery.py`: Added `confluence_only: bool = False` parameter, gated `jira_needed` behind it
3. `_cli_startup.py`: Caller passes `confluence_only=True`
4. `components/startup.py`: Caller passes `confluence_only=True`
5. `_flow_handlers.py`: `execute_restart_prd()` → `interactive=True`
6. Created 23 regression tests in `tests/flows/test_jira_approval_gate.py`

### Lesson Learned
Adding a safety gate parameter is not enough — it must be verified at
EVERY call site. When adding parameters that control security-critical
behavior, trace every caller chain end-to-end and add tests for each.

### Files Modified
- `src/.../flows/_finalization.py` — `confluence_only=True` in auto path
- `src/.../orchestrator/_startup_delivery.py` — `confluence_only` param
- `src/.../apis/slack/_flow_handlers.py` — `interactive=True` in restart
- `src/.../_cli_startup.py` — `confluence_only=True` propagation
- `src/.../components/startup.py` — `confluence_only=True` propagation
- `tests/flows/test_jira_approval_gate.py` — 23 regression tests (NEW)
- `tests/flows/test_prd_flow.py` — Updated 2 existing tests for new API
- `CODEX.md` — Jira Approval Gate invariant documented
- `obsidian/Architecture/Coding Standards.md` — §6 Jira approval gate
- `obsidian/Testing/Testing Guide.md` — Regression test documentation
- `obsidian/Orchestrator/Orchestrator Overview.md` — confluence_only docs
- `src/.../version.py` — v0.15.8

---

## Session 004 — 2026-03-09

**Scope**: Fix Confluence publish notification and Jira next-step flow
**Version**: v0.15.9

### Bugs Found (from production logs)
1. **No heartbeat during Confluence publish** — When user clicked "Publish to Confluence" from product list, `_handle_confluence_publish()` called `build_post_completion_crew()` without a `progress_callback`. Users saw a 2-4 minute silent gap.
2. **No Jira next-step notification** — After Confluence publish succeeded, the handler posted a success message but never offered the next step to create the Jira skeleton.
3. **Incorrect button label** — The `delivery_create_jira` button displayed "Create Jira Tickets" but the action always triggers skeleton generation (Phase 1 of the phased Jira workflow). Label should say "Create Jira Skeleton".

### Fixes Applied
- Added heartbeat `progress_callback` to `_handle_confluence_publish()` — posts crew step updates to Slack thread in real-time
- Added Jira next-step button after Confluence publish completes (only when Jira credentials configured)
- Changed button label from "Create Jira Tickets" to "Create Jira Skeleton" across all touchpoints:
  - `_delivery_action_blocks.py` — button text
  - `_dispatch.py` — ack message
  - `_flow_handlers.py` — fallback text
  - `_product_list_handler.py` — fallback text
  - `_delivery_action_handler.py` — docstring

### Key Lesson
The `delivery_create_jira` action_id always routes to `_do_create_jira()` → `_run_jira_phase(run_id, "skeleton", ...)`. The user-facing label must match the actual first phase of the phased workflow (skeleton), not the overarching capability (tickets).

### Tests Added/Modified
- `test_product_list.py` — 3 new tests in `TestHandleConfluencePublishHeartbeatAndNextStep`:
  - `test_progress_callback_posted_to_slack`
  - `test_jira_next_step_button_offered`
  - `test_no_jira_button_without_credentials`
- `test_delivery_action_blocks.py` — 1 new regression test: `test_button_label_says_skeleton`
- Updated existing tests to match new "Create Jira Skeleton" text

### Files Modified
- `src/.../apis/slack/blocks/_delivery_action_blocks.py` — Button label → "Create Jira Skeleton"
- `src/.../apis/slack/interactions_router/_dispatch.py` — Ack message → "Creating Jira skeleton"
- `src/.../apis/slack/interactions_router/_product_list_handler.py` — Added heartbeat + next-step button
- `src/.../apis/slack/interactions_router/_delivery_action_handler.py` — Updated docstring
- `src/.../apis/slack/_flow_handlers.py` — Fallback text → "Create Jira Skeleton"
- `tests/apis/slack/test_product_list.py` — 3 new tests + 2 assertion updates
- `tests/apis/slack/test_delivery_action_blocks.py` — 1 new regression test
- `obsidian/Integrations/Slack Integration.md` — Delivery action button description
- `obsidian/Integrations/Jira Integration.md` — Post-Confluence next step section

---

## Session 005 — 2026-03-09

**Scope**: Fix delivery state reset — scheduler overwrites confluence_published
**Version**: v0.15.9 → v0.15.10

### Bug Found (from production logs)
After Confluence publish succeeded, re-listing products showed "Publish to Confluence" again instead of "Start Jira Skeleton". The product list builder correctly checks `confluence_published`, but the field was being overwritten on every PublishScheduler sweep.

### Root Cause
`_discover_pending_deliveries()` in `_startup_delivery.py` had a data source mismatch. When `jira_phase == "subtasks_done"`, it called `upsert_delivery_record()` with:
```python
confluence_published=bool(doc.get("confluence_url"))  # from workingIdeas
```
But `save_confluence_url()` was removed from the codebase — the Confluence URL is only stored in the `productRequirements` delivery record, not `workingIdeas`. So `doc.get("confluence_url")` returned `None`, overwriting `confluence_published` from `True` to `False` on every scan.

The log evidence showed a repeating cycle:
1. `persist_post_completion()` saves `confluence_published=True` ✓
2. 5 min later: scheduler scan → `_discover_pending_deliveries()` → overwrites with `False` ✗
3. Next scan: `_discover_publishable_prds()` finds 1 without Confluence → RE-PUBLISHES

### Fixes Applied
1. **subtasks_done branch** — Only pass `jira_completed=True` to `upsert_delivery_record()`. No confluence fields, so existing state is preserved.
2. **Fully-done branch** — Read `confluence_url` from delivery record first, falling back to workingIdeas doc.
3. **Items dict** — Source `confluence_url` from delivery record instead of workingIdeas doc.

### Tests Added
- `test_marks_jira_completed_when_subtasks_done` — Updated to verify only `jira_completed` is passed
- `test_subtasks_done_preserves_confluence_state` — Regression: delivery record has `confluence_published=True` but workingIdeas has no URL → must NOT reset
- `test_fully_done_reads_confluence_url_from_delivery_record` — Regression: URL only in delivery record, not workingIdeas → must be sourced correctly
- `test_item_confluence_url_from_delivery_record` — Item dict inherits URL from delivery record

### Files Modified
- `src/.../orchestrator/_startup_delivery.py` — 3 fixes for data source mismatch
- `tests/orchestrator/test_startup_delivery.py` — 3 new regression tests + 1 updated test
- `src/.../version.py` — v0.15.10
- `obsidian/Changelog/Version History.md` — v0.15.10 entry
- `obsidian/Sessions/Session Log.md` — This entry

---

## Session 006 — 2026-03-09

**Scope**: Remove autonomous Jira detection; fix stale jira_phase data
**Version**: v0.15.10 → v0.15.11

### Bug Found (from production QA)
Product list showed ":white_check_mark: Jira Ticketing" for a product where Jira skeleton hadn't been started. User never approved any Jira creation.

### Root Cause
Bad data from autonomous Jira runs before the approval gate (v0.15.8). `persist_post_completion()` was detecting Jira keywords in crew output and autonomously setting `jira_phase=subtasks_done` + `jira_completed=True`, even for `confluence_only` crews. This violated the approval gate invariant.

### Data Fix
Created one-time script `scripts/fix_stale_jira_phase.py`:
1. Found docs with `jira_phase=subtasks_done` but no `jira_skeleton` (proving they weren't from interactive flow)
2. Reset `jira_phase=""` and `jira_completed=False`
3. Verified fix
4. Deleted script after use

### Code Fixes
Removed all autonomous Jira detection/persistence from 3 files:
- **`flows/_finalization.py`** — `persist_post_completion()` now only handles Confluence; no `jira_completed`, no `append_jira_ticket`, no `save_jira_phase`
- **`_cli_startup.py`** — Removed Jira detection block, ticket persistence, `save_jira_phase()` calls
- **`components/startup.py`** — Same cleanup as `_cli_startup.py`

### Tests Rewritten
- `test_prd_flow.py`: Replaced 3 old tests with 4 new tests verifying Jira is NOT detected/persisted
- `test_main.py`: Replaced `test_sets_jira_phase_subtasks_done_after_jira_completion` with `test_does_not_set_jira_phase_on_autonomous_path`
- `test_main.py`: Replaced `test_jira_output_not_written_to_working_ideas` with `test_no_jira_data_in_delivery_record_on_autonomous_path`
- `test_main.py`: Replaced `test_persists_ticket_type_from_jira_lookup` + `test_falls_back_to_unknown_when_search_fails` with `test_does_not_search_or_persist_jira_tickets`

### Documentation
- CODEX.md: Added "One-Time Data Fix Scripts" pattern (section 6) + v0.15.11 lesson learned to Jira Approval Gate
- Obsidian Coding Standards: Added section 7 (data fix scripts) + v0.15.11 lesson learned
- Obsidian Version History: v0.15.11 entry

### Files Modified
- `src/.../flows/_finalization.py` — Removed Jira detection from `persist_post_completion()`
- `src/.../\_cli_startup.py` — Removed Jira detection, ticket persistence, `save_jira_phase()`
- `src/.../components/startup.py` — Same cleanup
- `tests/flows/test_prd_flow.py` — 4 new approval-gate regression tests
- `tests/test_main.py` — 3 tests rewritten to assert Jira NOT persisted
- `tests/test_version.py` — Updated version assertion
- `src/.../version.py` — v0.15.11
- `CODEX.md` — Data fix pattern, recent changes, lesson learned
- `obsidian/Architecture/Coding Standards.md` — Data fix pattern + lesson learned
- `obsidian/Changelog/Version History.md` — v0.15.11 entry
- `obsidian/Sessions/Session Log.md` — This entry

---

## Session 007 — 2026-03-10

**Scope**: Jira Epics & Stories Output Persistence for Crash Resilience
**Version**: v0.15.11 → v0.15.12

### Problem
`jira_epics_stories_output` was only stored in-memory on `flow.state` and never persisted to MongoDB. If the server crashed after Phase 2 (Epics & Stories) but before Phase 3 (Sub-tasks), the Sub-tasks stage would skip because `flow.state.jira_epics_stories_output` was empty after resume. Additionally, `_run_jira_phase()` did not restore `jira_skeleton` or `jira_epics_stories_output` from MongoDB when reconstructing flow state.

### Fix
1. **New MongoDB functions** — `save_jira_epics_stories_output()` / `get_jira_epics_stories_output()` in `_status.py`, matching the skeleton persistence pattern
2. **Persist on creation** — `build_jira_epics_stories_stage._apply()` now calls `save_jira_epics_stories_output()` alongside `_persist_jira_phase()`
3. **Restore on resume** — `_run_jira_phase()` now restores `jira_skeleton` and `jira_epics_stories_output` from the MongoDB document during state reconstruction

### Tests Added (14 new, 2122 total)
- `TestSaveJiraEpicsStoriesOutput` (8 tests) — MongoDB save/get, error handling
- `TestEpicsStoriesStageApplyPersistence` (2 tests) — _apply persists output, survives save failure
- `TestSubtasksStageResume` (2 tests) — subtasks skips without output, does not skip with restored output
- `TestRunJiraPhaseStateReconstruction` (3 tests) — jira_skeleton restored, epics_stories_output restored, missing fields default to empty

### Files Modified
- `src/.../mongodb/working_ideas/_status.py` — Added save/get for jira_epics_stories_output
- `src/.../mongodb/working_ideas/repository.py` — Re-exported new functions
- `src/.../orchestrator/_jira.py` — Persist output in epics_stories _apply()
- `src/.../apis/slack/interactions_router/_product_list_handler.py` — Restore jira_skeleton + jira_epics_stories_output
- `tests/orchestrator/test_jira.py` — 4 new tests
- `tests/mongodb/working_ideas/test_repository.py` — 8 new tests
- `tests/apis/slack/test_product_list.py` — 3 new tests (state reconstruction)
- `src/.../version.py` — v0.15.12

---

## Session 007b — 2026-03-10

**Scope**: Eliminate 'unknown' Jira Ticket Types
**Version**: v0.15.12 → v0.15.13

### Problem
`JiraCreateIssueTool` persisted the raw LLM-provided `issue_type` to MongoDB before the orchestrator could write the correct hardcoded type. Since `append_jira_ticket()` deduplicates by key, the first (wrong) write won — resulting in "unknown", "Task", "Sub-Task", etc. in the database.

### Root Cause
Two code paths write tickets to MongoDB:
1. **JiraCreateIssueTool._run()** — writes during crew execution with whatever `issue_type` the LLM provides (first write wins)
2. **Orchestrator _jira.py** — writes after crew completes with hardcoded correct types, but dedup silently skips since key already exists

### Fix
Added `_normalise_issue_type()` in `_tool.py` that maps all LLM variants to canonical types before persistence:
- `"task"`, `"Task"` → `"Sub-task"`
- `"subtask"`, `"Sub-Task"` → `"Sub-task"`
- `"story"` → `"Story"`, `"epic"` → `"Epic"`
- `""`, `"unknown"`, unrecognised → `"Story"` (or `"Sub-task"` when `parent_key` is set)

### Tests Added (18 new, 2140 total)
- `TestNormaliseIssueType` (14 tests) — all variants and edge cases
- `TestToolNormalisesTypeBeforePersist` (4 tests) — end-to-end tool → MongoDB verification

### Files Modified
- `src/.../tools/jira/_tool.py` — Added `_normalise_issue_type()`, called in `_run()` before API call and persistence
- `tests/tools/test_jira_tool.py` — 18 new tests
- `src/.../version.py` — v0.15.13
- `tests/test_version.py` — Updated version assertion

---

## Session 007c — 2026-03-10

**Scope**: Add Archive Button to Product List
**Version**: v0.15.13 → v0.15.14

### Problem
The product list (completed ideas) had no way for users to archive an idea. Archive was only available in the idea list (in-progress ideas). Users could not remove completed products from future "list products" lookups.

### Fix
Added a `:file_folder: Archive #N` button to every product in the product list Block Kit builder. The button triggers a confirmation prompt (reusing the existing `archive_idea_confirm` / `archive_idea_cancel` flow). On confirmation, the working idea is marked `status="archived"` and excluded from future queries (which filter on `status="completed"`).

Changes:
1. **Block Kit builder** — Added archive button as the last element in every product's action row
2. **Dispatch router** — Added `product_archive_` to `_PRODUCT_PREFIXES` and ack label
3. **Product list handler** — Added `_handle_product_archive()` that looks up the product, posts confirmation blocks with the run_id, and reuses the existing archive confirmation flow

### Tests Added (11 new, 2151 total)
- `TestProductArchiveButton` (6 tests) — button presence, value format, ordering
- `TestProductArchiveAckLabel` (1 test) — dispatch ack label
- `TestProductArchiveHandler` (3 tests) — confirmation posting, error cases
- `TestProductArchiveDispatchRouting` (1 test) — prefix recognition

### Files Modified
- `src/.../apis/slack/blocks/_product_list_blocks.py` — Archive button added
- `src/.../apis/slack/interactions_router/_dispatch.py` — product_archive_ prefix + ack label
- `src/.../apis/slack/interactions_router/_product_list_handler.py` — _handle_product_archive()
- `tests/apis/slack/test_product_list.py` — 11 new tests
- `src/.../version.py` — v0.15.14
- `tests/test_version.py` — Updated version assertion

---

## Session 008 — 2026-03-10

**Scope**: Fix Progress Heartbeat Not Firing During Interactive PRD Flows
**Version**: v0.15.14 → v0.15.15

### Problem
During long-running PRD generation flows initiated via the interactive Slack path, users received no section-by-section progress updates. The heartbeat system (which posts messages like ":writing_hand: Drafting section 3/10: User Personas") was originally implemented but had stopped working for the interactive flow path.

### Root Cause
`run_interactive_slack_flow()` in `_flow_runner.py` never called `make_progress_poster()` to create a progress callback, and never set `flow.progress_callback`. The non-interactive path (`router.py` line 169) and resume path (`_flow_handlers.py` line 1031) both correctly created and wired the progress callback — only the interactive path was broken. Log evidence: `[Callbacks] progress=False` for interactive runs.

### Fix
Added to `_flow_runner.py`:
1. Import `make_progress_poster` from `_flow_handlers`
2. Create `progress_cb = make_progress_poster(channel, thread_ts, user, send_tool, run_id=run_id)`
3. Set `flow.progress_callback = progress_cb`
4. Include `"progress_callback": progress_cb` in the `_cb_kwargs` registry dict

### Tests Added (3 new, 2154 total)
- `test_progress_callback_set_on_flow` — verifies flow.progress_callback is set
- `test_progress_callback_registered_in_registry` — verifies register_callbacks includes progress_callback
- `test_make_progress_poster_called_with_correct_args` — verifies correct channel/thread/user/run_id passed

### Files Modified
- `src/.../apis/slack/interactive_handlers/_flow_runner.py` — Added progress_cb creation + registry wiring
- `tests/apis/slack/test_interactive_exec_completion.py` — 3 new tests
- `src/.../version.py` — v0.15.15
- `tests/test_version.py` — Updated version assertion

---

## Session 009 — 2026-03-10

**Scope**: Optimise PRD Section Generation Performance
**Version**: v0.15.15 → v0.16.0

### Problem
Log analysis of run 67aca7dc0697 showed section generation times growing dramatically:
- Problem Statement: 5 min (3 iterations)
- Non-Functional Requirements: 10 min (3 iterations)
- Edge Cases: 15 min (5 iterations)
- Error Handling: 21 min (3 iterations, draft alone 9 min)

### Root Causes
1. **Context bloat**: `approved_context()` sent full text of ALL prior approved sections to both critique and refine tasks. By section 7, prompts included ~30K+ chars of prior context.
2. **Executive summary double-counted**: Included in both `{executive_summary}` param AND in `{approved_sections}` (since it's the first approved section).
3. **Critic agent had knowledge_sources/embedder**: Unnecessary RAG overhead for a pure evaluation agent.

### Optimizations
1. **Condensed prior-section context for refine tasks** — New `approved_context_condensed()` method on PRDDraft sends only section titles + first 500 chars instead of full text. Applied only to refine tasks (research model = bottleneck). Critique tasks keep full context (flash model, needs duplication checking).
2. **Exclude executive_summary from approved_sections** — Both critique and refine tasks now pass `exclude_keys={"executive_summary", section.key}` since exec summary is already a separate template parameter.
3. **Remove knowledge_sources/embedder from critic** — Pure evaluation agent doesn't need RAG retrieval.

### Tests Added (4 new, 2158 total)
- `test_prd_draft_approved_context_exclude_keys` — multiple exclusion keys
- `test_prd_draft_approved_context_condensed` — truncation behavior
- `test_prd_draft_approved_context_condensed_exclude_keys` — condensed + exclusion
- `test_critic_no_knowledge_sources` — critic agent purity

### Files Modified
- `src/.../apis/prd/_domain.py` — Added `approved_context_condensed()`, updated `approved_context()` with `exclude_keys` param
- `src/.../flows/_section_loop.py` — Use condensed context for refine, exclude exec summary from both
- `src/.../agents/product_manager/agent.py` — Removed knowledge_sources/embedder from critic
- `tests/flows/test_prd_flow.py` — 3 new tests
- `tests/agents/test_product_manager.py` — 1 new test
- `src/.../version.py` — v0.16.0
- `tests/test_version.py` — Updated version assertion

---

## Session 010 — 2026-03-10

**Scope**: Fix Post-Completion Flow Not Prompting User After Resume
**Version**: v0.16.0 → v0.16.1

### Problem
After PRD sections completed via resume, Confluence and Jira tickets were created automatically without prompting the user. The `auto_approve=True` flag (intended only for section auto-acceptance) was causing the entire post-completion delivery to bypass approval gates.

### Root Cause
`handle_resume_prd()` in `_flow_handlers.py` called `resume_prd_flow(auto_approve=True)` without Jira callbacks. `resume_prd_flow()` in `service.py` didn't even accept Jira callback parameters. When `_finalization.py`'s `run_post_completion()` found no `jira_skeleton_approval_callback`, it fell to `_run_auto_post_completion()` which auto-published Confluence without user interaction.

### Fix
1. **service.py**: Added `jira_skeleton_approval_callback` and `jira_review_callback` params to `resume_prd_flow()`, wired to flow instance and callback registry
2. **_flow_handlers.py**: `handle_resume_prd()` now calls `register_interactive_run()`, builds Jira callbacks via factory functions, passes them to `resume_prd_flow()`, and cleans up via `cleanup_interactive_run()` in finally block

### Tests Added (5 new, 2150 total)
- `test_resume_builds_jira_callbacks` — handler builds factory callbacks with correct run_id
- `test_resume_registers_interactive_run` — handler stores channel/thread_ts for Slack callbacks
- `test_resume_jira_callbacks_wired_to_flow` — service wires callbacks to flow instance
- `test_resume_jira_callbacks_registered_in_registry` — service registers callbacks (spy before cleanup)
- `test_resume_without_jira_callbacks_omits_from_registry` — service omits absent callbacks

### Files Modified
- `src/.../apis/prd/service.py` — Added Jira callback params to `resume_prd_flow()`
- `src/.../apis/slack/_flow_handlers.py` — Wired interactive run + Jira callbacks in `handle_resume_prd()`
- `tests/flows/test_jira_approval_gate.py` — 2 new handler-level tests
- `tests/apis/prd/test_prd.py` — 3 new service-level tests
- `src/.../version.py` — v0.16.1

---

## Session 011 — 2026-03-10

**Scope**: Server Crash Resilience & Log-Driven Bug Fixes
**Version**: v0.16.1 → v0.16.2

### Problem
Server crashed during Jira ticket creation ("cannot schedule new futures after shutdown") and repeatedly restarted. Log analysis revealed three issues: (1) no auto-restart mechanism, (2) LLM hallucinated `run_id=RUN-12345` in Jira tickets, (3) `ShutdownError` swallowed in `_finalization.py`.

### Root Causes
1. **No auto-restart**: `start_server.sh` exits on crash with no recovery mechanism.
2. **LLM run_id hallucination**: The `run_id` was passed to the LLM in task description text. The LLM hallucinated "RUN-12345" when calling the Jira tool instead of using the actual value from the description.
3. **ShutdownError swallowed**: `run_post_completion()` in `_finalization.py` caught ALL exceptions including `ShutdownError`, `BillingError`, and `ModelBusyError` in a generic `except Exception` block, preventing the service layer from properly pausing the flow.

### Fixes
1. **start_server_watchdog.sh** (new): Auto-restart wrapper with signal handling (SIGINT/SIGTERM → clean shutdown, no restart), circuit breaker (5 restarts in 120s → stop), logging to `logs/watchdog.log`.
2. **authoritative_run_id on JiraCreateIssueTool**: Added `authoritative_run_id` field set at construction time. When set, it overrides whatever `run_id` the LLM provides — same pattern as `_resolve_confluence_url`. Wired through `create_jira_product_manager_agent(run_id=)` and `create_jira_architect_tech_lead_agent(run_id=)`, called from `_jira.py` stages with `flow.state.run_id`.
3. **Re-raise critical errors**: Added `except (BillingError, ModelBusyError, ShutdownError): raise` before the generic `except Exception` in `run_post_completion()`.
4. **Fixed 7 flaky retry tests**: Pre-existing test pollution from background threads calling `time.sleep()`. Changed `assert_called_once_with` → `assert_any_call` and `assert_not_called` → filtered call list checks.

### Tests Added (12 new, 2175 total)
- `TestAuthoritativeRunId` (5 tests): override LLM run_id, use LLM when empty, authoritative when LLM empty, default empty, construction
- `TestRunPostCompletion` (3 tests): shutdown_error_propagates, billing_error_propagates, model_busy_error_propagates
- `TestJiraAgentRunId` (4 tests): PM/Architect agent pass run_id to tool, default empty

### Files Modified
- `start_server_watchdog.sh` — NEW: auto-restart wrapper
- `src/.../tools/jira/_tool.py` — Added `authoritative_run_id` field + override logic
- `src/.../agents/orchestrator/agent.py` — Added `run_id` param to Jira agent factories
- `src/.../orchestrator/_jira.py` — Pass `flow.state.run_id` to agent factories
- `src/.../flows/_finalization.py` — Re-raise ShutdownError/BillingError/ModelBusyError
- `tests/tools/test_jira_tool.py` — 5 new tests (TestAuthoritativeRunId)
- `tests/flows/test_prd_flow.py` — 3 new tests (error propagation)
- `tests/agents/test_orchestrator.py` — 4 new tests (TestJiraAgentRunId)
- `tests/test_retry.py` — Fixed flaky assertion
- `tests/tools/test_gemini_chat.py` — Fixed 3 flaky assertions
- `tests/tools/test_openai_chat.py` — Fixed 3 flaky assertions
- `src/.../version.py` — v0.16.2

---

## Session 012 — 2026-03-10

**Scope**: CODEX.md Optimization & Obsidian Knowledge Base Restructuring
**Version**: v0.16.2 (no version change — documentation only)

### Work Done
1. **Created `obsidian/Architecture/CrewAI Framework.md`** — Comprehensive page mapping CrewAI core concepts (Agents, Tasks, Crews, Flows, Tools, Knowledge, Memory) to project implementation. Includes concept table, agent definitions, task patterns, crew instances, PRDFlow architecture, custom tools, knowledge files, memory usage, and 6 design principles. Sourced from official docs at docs.crewai.com.
2. **Optimized CODEX.md** — Reduced from ~750 lines to ~210 lines by removing all content duplicated in Obsidian:
   - Removed: Server Lifecycle details, PRD Flow Progress Events, Slack Module Map, MongoDB Module Map, Orchestrator Module Map, Test Module Map, full Coding Standards, full Session Management, Obsidian vault structure listing, Project Conventions, LLM Model Tiers, Environment Variables
   - Removed: Entire "Recent Changes" changelog (~120 lines) — kept only in `Changelog/Version History.md`
   - Kept: Quick Reference table, Obsidian lookup table, "When to load which file" table, PRD Service table, Quick Start, Common Commands, Coding Standards summary, Session Management summary, Patch Target Cheat Sheet
   - Added: Obsidian Knowledge Base section with topic-to-page lookup table and "When to Update Which Page" reference
3. **Updated `obsidian/Home.md`** — Version 0.15.4 → 0.16.2, added `[[CrewAI Framework]]` and `[[Coding Standards]]` links, updated vault structure listing
4. **Updated `obsidian/Testing/Testing Guide.md`** — Test count 2033+ → 2175+

### Key Decisions
- CODEX.md is now a lean lookup guide: quick-reference tables + Obsidian pointers
- All detailed documentation lives exclusively in Obsidian
- Changelog removed from CODEX.md entirely — single source of truth in `Version History.md`
- CrewAI Framework page serves as the bridge between official CrewAI docs and our implementation

### Files Modified
- `CODEX.md` — Rewritten from ~750 to ~210 lines
- `obsidian/Architecture/CrewAI Framework.md` — NEW
- `obsidian/Home.md` — Version + links + vault structure updated
- `obsidian/Testing/Testing Guide.md` — Test count updated
- `obsidian/Sessions/Session Log.md` — This entry

---

## Session 005 — 2026-03-13

**Scope**: MongoDB Atlas Migration
**Version**: v0.16.2 → v0.17.0

### Work Done
1. **Refactored `mongodb/client.py`** — Replaced localhost-based URI building (`MONGODB_URI`, `MONGODB_PORT`, `MONGODB_USERNAME`, `MONGODB_PASSWORD`) with single `MONGODB_ATLAS_URI` env var. `_build_uri()` now returns the Atlas connection string directly; raises `RuntimeError` if not set.
2. **Updated `mongodb/__init__.py`** — Removed `DEFAULT_HOST` and `DEFAULT_PORT` exports (no longer exist).
3. **Updated `scripts/preflight.py`** — `check_mongodb()` now validates `MONGODB_ATLAS_URI` instead of `MONGODB_URI`.
4. **Updated `.env`** — Removed old `MONGODB_URI`, `MONGODB_PORT`, `MONGODB_USERNAME`, `MONGODB_PASSWORD` vars. `MONGODB_ATLAS_URI` is the sole connection config.
5. **Created `scripts/migrate_to_atlas.py`** — One-time migration script that exports all collections (with indexes) from localhost MongoDB to Atlas. Supports `--dry-run`, `--source` customization, batch insert with duplicate-key resilience.
6. **Rewrote `tests/mongodb/test_client.py`** — 9 new tests covering Atlas URI validation, whitespace stripping, missing/empty URI errors, and `_get_db_name` behaviour.
7. **Updated Obsidian docs** — Environment Variables (Atlas URI), MongoDB Schema (Atlas hosted note).

### Key Decisions
- `MONGODB_ATLAS_URI` is required — no fallback to localhost. This ensures the application cannot accidentally connect to a local database in production.
- Migration script preserves `_id` values for data consistency across environments.
- `MONGODB_DB` still defaults to `ideas` for database name flexibility.

### Files Modified
- `src/crewai_productfeature_planner/mongodb/client.py`
- `src/crewai_productfeature_planner/mongodb/__init__.py`
- `src/crewai_productfeature_planner/scripts/preflight.py`
- `src/crewai_productfeature_planner/version.py`
- `.env`
- `scripts/migrate_to_atlas.py` — NEW
- `tests/mongodb/test_client.py`
- `obsidian/Architecture/Environment Variables.md`
- `obsidian/Database/MongoDB Schema.md`
- `obsidian/Sessions/Session Log.md` — This entry

---

## Session 008 — 2026-03-13

**Scope**: Fix Intent Misclassification (idea → create_jira)
**Version**: v0.17.0 → v0.17.1

### Problem
When a user submitted a long idea via Slack that contained phrases like "jira tickets" or "jira epics" in the idea body, the phrase override chain in `_message_handler.py` reclassified the intent from `create_prd` (correctly identified by the LLM) to `create_jira`. This caused the system to skip the entire PRD generation pipeline and jump straight to Jira ticket creation.

### Root Cause
In the phrase override chain (`_message_handler.py` ~line 196), `has_create_jira_phrase` was checked **before** `has_idea_phrase`. Since `_CREATE_JIRA_PHRASES` includes substrings like `"jira tickets"` and `"jira epics"`, long idea text containing those words as part of the description (not as a command) triggered the override, replacing the correct LLM classification.

### Fix
1. Reordered the phrase override chain: `has_idea_phrase` now checked before `has_create_jira_phrase`
2. Added guard: `has_create_jira_phrase and intent != "create_prd"` — when the LLM correctly classifies as `create_prd`, the jira phrase override is suppressed

### Files Modified
- `src/crewai_productfeature_planner/apis/slack/_message_handler.py` — phrase override reorder + LLM trust guard
- `tests/apis/slack/test_create_jira_intent.py` — 3 new regression tests
- `src/crewai_productfeature_planner/version.py` — 0.17.1 codex entry
- `obsidian/Sessions/Session Log.md` — This entry

### Tests
- 605 Slack tests passed (602 existing + 3 new regression tests)
- 25 Jira approval gate tests passed

---

## Session 009 — 2026-03-13

**Scope**: GStack Agent Integration
**Version**: v0.17.1 → v0.18.0

### Summary
Integrated 7 gstack-inspired agent roles into CrewAI. Introduced Phase 1.5 (CEO Reviewer → `executive_product_summary`, Eng Manager → `engineering_plan`). Both artefacts feed Phase 2 section drafting and Jira context. SECTION_ORDER expanded from 10 to 12 sections. 5 stub agents created for future activation.

### Tests
- 12 new tests in `test_ceo_eng_review.py`
- 2162 total tests passing

---

## Session 010 — 2026-03-13

**Scope**: Jira Review & QA Test Sub-tasks
**Version**: v0.18.0 → v0.19.0

### Summary
Extended the 3-phase Jira pipeline to 5 phases. Activated 3 stub agents (Staff Engineer, QA Lead, QA Engineer) with full factories, task YAML configs, and JiraCreateIssueTool.

### Changes
1. **Phase 4: Review Sub-tasks** — Staff Engineer + QA Lead review every user story as sub-tasks. Staff Eng performs structural audit (N+1 queries, race conditions, trust boundaries, missing indexes). QA Lead performs test methodology review (acceptance criteria, coverage gaps, negative tests, regression risk).
2. **Phase 5: QA Test Sub-tasks** — QA Engineer creates `[QA Test]` counter-tickets per implementation sub-task covering edge cases, security (injection, auth bypass, CSRF/SSRF), and rendering (empty/loading/error states, responsive, accessibility).
3. **Jira Phase State Machine** — Extended: `subtasks_done → review_ready → review_done → qa_test_ready → qa_test_done`
4. **Slack Integration** — 6 new phase labels, 5 new button blocks, 4 new approval handlers

### Files Created
- `agents/staff_engineer/agent.py` — Full factory with `create_staff_engineer()`
- `agents/staff_engineer/config/tasks.yaml` — Structural audit task template
- `agents/qa_lead/agent.py` — Full factory with `create_qa_lead()`
- `agents/qa_lead/config/tasks.yaml` — Test methodology review task template
- `agents/qa_engineer/agent.py` — Full factory with `create_qa_engineer()`
- `agents/qa_engineer/config/tasks.yaml` — Edge case/security test task template

### Files Modified
- `orchestrator/_jira.py` — Phase 4 + 5 stage builders, updated auto-approve chain
- `flows/_constants.py` — `jira_review_output`, `jira_qa_test_output` fields
- `flows/_finalization.py` — Phase 4 + 5 execution blocks
- `apis/slack/blocks/_product_list_blocks.py` — Phase labels + buttons
- `apis/slack/interactions_router/_product_list_handler.py` — Reviews/QA tests branches
- `apis/slack/interactions_router/_jira_approval_handler.py` — 4 new handlers, dispatch
- `orchestrator/stages.py`, `orchestrator/__init__.py` — Re-exports

### Tests
- 2162 tests passing (3 tests updated for new 5-phase behavior)

---

## Session 009 — 2026-03-13

**Scope**: GStack Agent Integration (CEO Reviewer + Eng Manager + Phase 1.5)
**Version**: v0.17.1 → v0.18.0

### Summary
Integrated 7 gstack-inspired agent roles into the CrewAI project and added a new Phase 1.5 to the PRD flow. After the executive summary is approved, the CEO Reviewer agent generates an `executive_product_summary` (10-star product vision), and the Eng Manager agent produces an `engineering_plan` (technical architecture). Both artefacts feed into Phase 2 section drafting and Jira ticket creation.

### New Agent Directories
- `agents/ceo_reviewer/` — Full agent (YAML + factory + tasks)
- `agents/eng_manager/` — Full agent (YAML + factory + tasks)
- `agents/staff_engineer/` — Stub
- `agents/release_engineer/` — Stub
- `agents/qa_engineer/` — Stub
- `agents/qa_lead/` — Stub
- `agents/retro_manager/` — Stub

### New Files
- `flows/_ceo_eng_review.py` — `run_ceo_review()` and `run_eng_plan()` for Phase 1.5
- `tests/flows/test_ceo_eng_review.py` — 12 tests covering both functions

### Files Modified
- `apis/prd/_sections.py` — SECTION_ORDER expanded (10→12), added SPECIALIST_SECTION_KEYS
- `flows/_constants.py` — PRDState fields: `executive_product_summary`, `engineering_plan`
- `flows/prd_flow.py` — Phase 1.5a/1.5b insertion, parallel drafting context
- `flows/_agents.py` — `run_agents_parallel()` signature + format calls
- `flows/_section_loop.py` — critique/refine template vars, _excl set
- `agents/product_manager/config/tasks.yaml` — section tasks use new template vars
- `orchestrator/_jira.py` — `_build_jira_context()` helper, engineering plan injection
- `components/resume.py` — specialist section restoration
- `apis/prd/service.py` — specialist fields in resume_prd_flow
- `tests/flows/test_prd_flow.py` — 57 format string replacements, section index fixes, CEO/Eng mocks
- `tests/apis/prd/test_prd.py` — sections_total 10→12, next_section assertions
- `version.py` — 0.18.0 codex entry

### Tests
- 2162 total tests passing (12 new in test_ceo_eng_review.py)

---

## Session 011 — 2026-03-13

**Scope**: UX Designer Agent & Figma Make Integration (Phase 1.5c)
**Version**: v0.19.0 → v0.20.0

### Summary
Created a UX Designer agent that runs after the Executive Product Summary (Phase 1.5c). The agent converts the summary into a structured Figma Make prompt and submits it to the Figma Make API to generate clickable prototypes. When Figma credentials are unavailable, the generated prompt is stored for manual use. The Figma design URL and status are persisted to MongoDB and shown in the Slack product list with status indicators and action buttons. Both the UX design and engineering plan now feed into all Jira ticket generation stages.

### New Files
- `tools/figma/__init__.py` — Package exports (FigmaMakeTool)
- `tools/figma/_config.py` — Env helpers: FIGMA_ACCESS_TOKEN, FIGMA_TEAM_ID, has_figma_credentials()
- `tools/figma/_client.py` — HTTP client: submit_figma_make(), poll_figma_make(), FigmaMakeError
- `tools/figma/figma_make_tool.py` — CrewAI BaseTool wrapper with FIGMA_URL/SKIPPED/ERROR output
- `agents/ux_designer/__init__.py` — Package exports
- `agents/ux_designer/agent.py` — Factory with _build_llm() (research tier), create_ux_designer()
- `agents/ux_designer/config/agent.yaml` — Senior UX Designer role/goal/backstory
- `agents/ux_designer/config/tasks.yaml` — 6-step Figma Make prompt generation task
- `flows/_ux_design.py` — run_ux_design() with output parsing and MongoDB persistence
- `tests/tools/test_figma_tool.py` — 29 tests for Figma config, client, and tool
- `tests/flows/test_ux_design.py` — 10 tests for UX design flow

### Files Modified
- `flows/_constants.py` — 3 new PRDState fields: figma_design_url, figma_design_prompt, figma_design_status
- `flows/prd_flow.py` — Phase 1.5c insertion after Eng Plan (1.5b)
- `mongodb/working_ideas/_status.py` — save_figma_design() function
- `mongodb/working_ideas/repository.py` — Re-export save_figma_design
- `mongodb/working_ideas/_queries.py` — figma fields in _doc_to_product_dict()
- `apis/slack/blocks/_product_list_blocks.py` — Figma status indicators + buttons
- `apis/slack/interactions_router/_product_list_handler.py` — _handle_ux_design() + figma field restoration in _run_jira_phase()
- `apis/slack/interactions_router/_dispatch.py` — product_ux_design_ ack label
- `orchestrator/_jira.py` — _build_jira_context() includes UX design blocks
- `tests/flows/test_ceo_eng_review.py` — 5 new Jira context UX tests
- `tests/apis/slack/test_product_list.py` — 11 new Figma block, handler, and state tests
- `version.py` — 0.20.0 codex entry

### New Environment Variables
- `FIGMA_ACCESS_TOKEN` — Figma API personal access token
- `FIGMA_TEAM_ID` — Figma team ID for design file creation
- `GEMINI_UX_DESIGNER_MODEL` — Optional LLM model override for UX Designer

### Tests
- 2217 total tests passing (55 new)

---

## Session 017 — 2026-03-15

**Scope**: Resume Gate Bypass Fix
**Version**: v0.20.0 → v0.20.1

### Problem
Resumed PRD flows got stuck at two approval gates:
1. **Requirements approval gate** — `_requires_approval()` only checked `any(s.content for s in draft.sections)`, which returned False when specialist sections (CEO, Eng, UX) had content but regular sections hadn't started yet.
2. **"Proceed to sections?" gate** — always fired on resume even when all specialist agents had already run, causing a 10-minute timeout before continuing.

Combined, these two gates consumed 20 minutes of timeout on every resume, often causing the server to restart before Phase 2 could begin.

### Root Cause
- `_requires_approval()` in `_requirements.py` didn't account for specialist agent state (`executive_product_summary`, `engineering_plan`, `figma_design_status`)
- The user decision gate in `prd_flow.py` had no skip logic for resumed runs where specialists already completed

### Work Done
- **`orchestrator/_requirements.py`**: Added specialist state checks to `_requires_approval()` — auto-approves when `executive_product_summary`, `engineering_plan`, or `figma_design_status` are set
- **`flows/prd_flow.py`**: Added `specialists_all_skipped` flag tracking whether all three specialist steps were skipped (resume case). User decision gate now bypassed when `specialists_all_skipped` or `has_section_content` is true
- **`tests/flows/test_prd_flow.py`**: Fixed `test_callback_false_raises_completed` — added `_has_gemini_credentials` mock and `monkeypatch.delenv` for Gemini API keys so specialist agents don't hit live API. Removed pre-populated specialist state from `test_requirements_approval_callback_continue_proceeds` to match new gate behavior
- **`version.py`**: v0.20.1 codex entry

### Files Modified
- `src/crewai_productfeature_planner/orchestrator/_requirements.py`
- `src/crewai_productfeature_planner/flows/prd_flow.py`
- `tests/flows/test_prd_flow.py`
- `src/crewai_productfeature_planner/version.py`

### Tests
- All existing tests passing (163 flow + 162 orchestrator + 81 API + 277 agent tests verified)

---

## Session 018 — 2026-03-16

**Scope**: Retry UX Design dispatch fix + test performance
**Version**: v0.20.1 → v0.20.2

### Problem 1 — Retry UX Design button click ignored
The "Retry UX Design" button in the Slack product list did nothing when clicked. The button was correctly rendered with `action_id=product_ux_design_<N>`, and the handler `_handle_ux_design()` was fully implemented, but the dispatcher's `_PRODUCT_PREFIXES` tuple was missing `"product_ux_design_"` — so the click was silently dropped.

### Problem 2 — Test suite taking 199s (6 tests at 25-28s each)
Six end-to-end `generate_sections()` tests in `test_prd_flow.py` were calling the live Gemini API via the unmocked `_run_ux_design()` method. Each test waited ~25s for the real UX Designer agent to generate a Figma Make prompt.

### Work Done
- **`_dispatch.py`**: Added `"product_ux_design_"` to `_PRODUCT_PREFIXES`
- **`test_product_list.py`**: Added `test_ux_design_prefix_in_product_prefixes` regression test
- **`test_prd_flow.py`**: Added `_run_ux_design` mock to 3 tests and `figma_design_status = "prompt_ready"` to 3 tests

### Files Modified
- `src/crewai_productfeature_planner/apis/slack/interactions_router/_dispatch.py`
- `tests/apis/slack/test_product_list.py`
- `tests/flows/test_prd_flow.py`
- `src/crewai_productfeature_planner/version.py`

### Tests
- 2205 passed, full suite: 199s → 32s (84% faster)

---

## Session 019 — 2026-03-16

**Scope**: Figma Make — Playwright browser automation
**Version**: v0.20.2 → v0.21.0

### Problem
The `_client.py` used `POST /v1/ai/make` against the Figma REST API, but this endpoint **does not exist** — confirmed by fetching the Figma OpenAPI spec. The `/v1/ai/make` endpoint was fabricated by the LLM that originally wrote the tool.

### Solution
Replaced the urllib-based HTTP client with **Playwright headless Chromium** automation that drives the Figma Make web UI at `figma.com/make/new`.

### Work Done
- **`_config.py`**: Complete rewrite — removed `FIGMA_API_BASE`, `DEFAULT_POLL_INTERVAL`, `DEFAULT_POLL_TIMEOUT`, `get_figma_access_token()`, `get_figma_team_id()`. Added `FIGMA_MAKE_URL`, `DEFAULT_MAKE_TIMEOUT`, `DEFAULT_SESSION_DIR`, `get_figma_session_dir()`, `get_figma_session_path()`, `get_figma_make_timeout()`, `get_figma_headless()`. Updated `has_figma_credentials()` to check for Playwright session state file.
- **`_client.py`**: Complete rewrite — removed `_request()`, `submit_figma_make()`, `poll_figma_make()`. Added `run_figma_make(prompt)` using Playwright: launch Chromium → load session state → navigate to `/make/new` → detect login redirect → find chat input → fill prompt → press Enter/click Send → wait for URL change → wait for networkidle → return file URL. Helper functions: `_find_chat_input()`, `_send_prompt()`, `_wait_for_generation()`.
- **`figma_make_tool.py`**: Updated imports from `submit_figma_make`/`poll_figma_make` to `run_figma_make`. Simplified `_run()` to single function call. Updated skip message.
- **`__init__.py`**: Updated docstring for Playwright approach and new env vars.
- **`login.py`**: New interactive login script — opens visible Chromium for manual Figma login, saves Playwright `storage_state()` to session dir.
- **`_product_list_handler.py`**: Updated "FIGMA_ACCESS_TOKEN" message to login script instructions.
- **`pyproject.toml`**: Added `playwright>=1.40` dependency.
- **`test_figma_tool.py`**: Complete rewrite — 32 tests covering config, client helpers, `run_figma_make`, and `FigmaMakeTool` with Playwright mocks.

### Env Var Changes
| Removed | Added |
|---------|-------|
| `FIGMA_ACCESS_TOKEN` | `FIGMA_SESSION_DIR` (default `~/.figma_session`) |
| `FIGMA_TEAM_ID` | `FIGMA_MAKE_TIMEOUT` (default 300) |
| `FIGMA_API_BASE` | `FIGMA_HEADLESS` (default `"true"`) |

### Auth Approach
Playwright `storage_state()` JSON file saved from one-time interactive login session via `login.py`. Reused automatically for headless automation.

### Files Modified
- `src/.../tools/figma/_config.py` (rewritten)
- `src/.../tools/figma/_client.py` (rewritten)
- `src/.../tools/figma/figma_make_tool.py` (updated)
- `src/.../tools/figma/__init__.py` (updated)
- `src/.../tools/figma/login.py` (new)
- `src/.../apis/slack/interactions_router/_product_list_handler.py` (updated)
- `pyproject.toml` (updated)
- `tests/tools/test_figma_tool.py` (rewritten)
- `src/.../version.py` (bumped to 0.21.0)

### Tests
- 2221 passed in 37s (net +16 from test rewrite)

---

## Session 019 — 2026-03-16

**Scope**: Figma Project Config + OAuth + REST API
**Version**: v0.21.1 → v0.22.0

### Work Done
- Added 5 Figma fields to `projectConfig` MongoDB schema: `figma_api_key`, `figma_team_id`, `figma_oauth_token`, `figma_oauth_refresh_token`, `figma_oauth_expires_at`
- Created `_api.py` — Figma REST API client (`get_team_projects`, `get_project_files`, `get_file_info`, `refresh_oauth_token`, `exchange_oauth_code`)
- Updated `_config.py` — project-level credential resolution chain (API key → OAuth token → Playwright session). New: `get_figma_credentials()`, `has_figma_credentials(project_config)`, `_oauth_expired()`, `get_figma_client_id()`, `get_figma_client_secret()`, `FIGMA_OAUTH_URL`, `OAUTH_REDIRECT_URI`
- Updated `_client.py` — OAuth token cookie injection via `_build_context()`. `run_figma_make()` now accepts `project_config` kwarg.
- Rewritten `login.py` — dual mode: `--oauth` flag for OAuth2 flow (local HTTP server + Playwright consent), default session login unchanged
- Setup wizard expanded from 2 to 4 steps: added `figma_api_key` and `figma_team_id`
- Wired `project_config` through agent → tool pipeline: `_ux_design.py` → `create_ux_designer(project_config=...)` → `FigmaMakeTool._project_config`
- Expanded tests from 32 to 64 for Figma module, updated setup wizard tests

### New Env Vars
| Variable | Purpose |
|----------|---------|
| `FIGMA_CLIENT_ID` | OAuth2 app client ID |
| `FIGMA_CLIENT_SECRET` | OAuth2 app client secret |

### Files Modified
- `src/.../mongodb/project_config/repository.py` (schema + create_project)
- `src/.../tools/figma/_api.py` (new)
- `src/.../tools/figma/_config.py` (rewritten)
- `src/.../tools/figma/_client.py` (rewritten)
- `src/.../tools/figma/login.py` (rewritten)
- `src/.../tools/figma/figma_make_tool.py` (updated)
- `src/.../tools/figma/__init__.py` (updated)
- `src/.../apis/slack/session_manager.py` (4 setup steps)
- `src/.../apis/slack/blocks/_session_blocks.py` (Figma step labels + summary)
- `src/.../apis/slack/_session_project.py` (persist Figma keys)
- `src/.../agents/ux_designer/agent.py` (project_config injection)
- `src/.../flows/_ux_design.py` (load project config)
- `tests/tools/test_figma_tool.py` (expanded)
- `tests/apis/slack/test_interaction_tracking.py` (updated for 4 steps)
- `src/.../version.py` (bumped to 0.22.0)

### Tests
- 2253 passed in 38s (net +32 from new Figma tests)

---

## Session 020 — 2026-03-16

**Scope**: Project Config Reconfiguration Wizard + Config Button
**Version**: v0.22.0 → v0.22.1

### Work Done
- Expanded `_UPDATE_CONFIG_PHRASES` from 12 to 21 phrases — added "project config", "project configuration", "configure project", "edit config", "edit project config", "change config", "reconfigure", "reconfigure project", "update project config", "project settings", "edit settings"
- Rewrote `handle_update_config()` from inline field updater to full 5-step setup wizard launcher with pre-populated current values
- Expanded `_SETUP_STEPS` from 4 to 5: added `project_name` as first step
- New `_NEW_PROJECT_START_STEP = "confluence_space_key"` — new project creation skips project_name step
- New `mark_pending_reconfig()` in `session_manager.py` — starts wizard at step 0 (project_name) with existing config pre-populated
- Added `current_value` parameter to `project_setup_step_blocks()` — shows "Current value: `X`" hint during reconfiguration
- Added `:gear: Config` button to product list header (action_id `product_config`, block_id `product_project_actions_{project_id}`)
- Added `product_config` action routing in `_dispatch.py` → `_handle_product_config()` in `_product_list_handler.py`
- `handle_project_setup_reply()` now handles `project_name` step; skip preserves existing name

### Files Modified
- `src/.../apis/slack/_intent_phrases.py` — 9 new config phrases
- `src/.../apis/slack/session_manager.py` — 5-step tuple, `_NEW_PROJECT_START_STEP`, `mark_pending_reconfig()`
- `src/.../apis/slack/blocks/_session_blocks.py` — `project_name` label, `current_value` param
- `src/.../apis/slack/_session_project.py` — project_name handling, skip preservation, name persistence
- `src/.../apis/slack/_session_memory.py` — `handle_update_config()` rewritten as wizard launcher
- `src/.../apis/slack/blocks/_product_list_blocks.py` — Config button at project level
- `src/.../apis/slack/interactions_router/_dispatch.py` — `product_config` action routing
- `src/.../apis/slack/interactions_router/_product_list_handler.py` — `_handle_product_config()`
- `tests/apis/slack/test_interaction_tracking.py` — 4 new reconfig tests, assertion fix
- `tests/apis/slack/test_product_list.py` — `_product_action_blocks()` helper, Config button test
- `tests/apis/slack/test_configure_memory_intent.py` — phrase override + fallback tests
- `src/.../version.py` — bumped to 0.22.1

### Tests
- 2260 passed in 41s (net +7 new tests)

---

## Session 021 — 2026-03-16

**Scope**: LLM Token Optimisation + Manual UX Design
**Version**: v0.22.1 → v0.22.2

### Work Done

#### LLM Token Reduction
- **Critique task**: Switched from `approved_context()` (full verbatim text of all approved sections) to `approved_context_condensed(char_limit=300)` — saves ~5,000–30,000 chars/call on later sections
- **EPS/Eng Plan in critique**: New `condensed_text()` helper in `_domain.py` truncates to 1500 chars for critique calls (critic evaluates quality, doesn't write content — full text unnecessary)
- **Refine expected_output**: Removed unused `critique_section_content` kwarg from `.format()` call — YAML template only uses `{section_title}`
- **Estimated savings**: ~50-70% token reduction per critique call on later sections; ~20-30% overall LLM cost reduction across full PRD generation

#### Manual UX Design
- Added `:page_facing_up: Manual UX Design` button alongside existing UX design button in product list
- Button appears whenever API UX design button appears (start or retry state)
- New `_handle_manual_ux_design()` handler loads EPS + ux_design section from MongoDB, builds formatted markdown, uploads as Slack file snippet
- Fallback to plain text if file upload fails

### Files Modified
- `src/.../apis/prd/_domain.py` — Added `condensed_text()` helper
- `src/.../flows/_section_loop.py` — Critique uses condensed context, condensed EPS/eng plan; refine drops unused kwarg
- `src/.../apis/slack/blocks/_product_list_blocks.py` — Manual UX Design button
- `src/.../apis/slack/interactions_router/_dispatch.py` — `product_manual_ux_` prefix + ack label
- `src/.../apis/slack/interactions_router/_product_list_handler.py` — `_handle_manual_ux_design()`
- `src/.../agents/product_manager/config/tasks.yaml` — No changes (templates already clean)
- `tests/flows/test_prd_flow.py` — 5 `condensed_text` tests; 21 test task_configs updated (removed `{critique_section_content}` from expected_output)
- `tests/apis/slack/test_product_list.py` — Manual UX button tests, dispatch tests, handler tests
- `src/.../version.py` — bumped to 0.22.2

### Tests
- 2271 passed in 37s (net +11 new tests)

---

## Session 014 — 2026-03-16

**Scope**: Fix UX Design task generating no user-visible output
**Version**: v0.22.2 → v0.22.3

### Root Cause
Two issues caused the UX Design Phase 1.5c to produce no value:

1. **Agent didn't always output the prompt** — Task YAML only instructed agent to output `FIGMA_PROMPT:` when tool returned `FIGMA_SKIPPED`. When Figma API returned HTTP 404 (`FIGMA_ERROR`), the agent relayed only the 74-char error with zero design content (22:02 run on 2026-03-15). Status → `skipped`, nothing useful stored.
2. **Even when prompt was generated, it was never delivered** — The first run (15:31) DID generate a 5096-char prompt stored as `prompt_ready`, but: SECTION_ORDER doesn't include `ux_design` → `assemble()` never includes it; Slack message just said "Figma prompt generated" without sharing content; no standalone file written; buried in MongoDB.

### Fixes Applied
1. **Task YAML** (`agents/ux_designer/config/tasks.yaml`) — Agent now MUST ALWAYS output `FIGMA_PROMPT:` with full design spec regardless of tool success/error/skip. The prompt is described as valuable UX spec included in the PRD.
2. **Error recovery** (`flows/_ux_design.py`) — When `FIGMA_ERROR` is present but no `FIGMA_PROMPT`, strips error markers and stores remainder as prompt if >100 chars of design content exists. Previously marked as `skipped` and discarded everything.
3. **PRD appendix** (`flows/_finalization.py`) — `finalize()` appends "Appendix: UX Design" section to assembled PRD with Figma URL (if any) and full prompt. `save_progress()` also includes it in draft files.
4. **Standalone file** (`flows/_ux_design.py`) — New `_save_ux_design_file()` writes `ux_design_*.md` alongside PRDs in `output/prds/YYYY/MM/` when prompt is generated.
5. **Slack notification** (`apis/slack/_flow_handlers.py`) — `ux_design_complete` handler now includes prompt preview (300 chars) and tells user the spec is in the PRD appendix and saved as standalone file. Progress event payload now includes `prompt_preview`.

### Files Modified
- `src/.../agents/ux_designer/config/tasks.yaml` — Mandatory FIGMA_PROMPT output
- `src/.../flows/_ux_design.py` — Error recovery, standalone file write, prompt_preview in event
- `src/.../flows/_finalization.py` — UX Design appendix in finalize() and save_progress()
- `src/.../apis/slack/_flow_handlers.py` — Richer ux_design_complete notification
- `tests/flows/test_ux_design.py` — Updated assertions for new payload, added error recovery test
- `src/.../version.py` — Bumped to 0.22.3

### Tests
- 2272 passed (net +1 new test: `test_error_with_long_content_recovers_prompt`)

---

## Session 015 — SSO "Idea Foundry" Application Whitelisting
**Date**: 2026-03-16 | **Version**: 0.22.3 → 0.23.0

### Goal
Register "Idea Foundry" as the application name in the SSO platform and update the PRD planner to validate tokens were issued for this application. Both sides must acknowledge the whitelisted application.

### Changes

#### SSO side (`c9s_singlesignon`)
1. **`applications_repo.py`** — Added `find_app_by_name()` for case-insensitive app lookup by name.
2. **`bootstrap.py`** — Seeds "Idea Foundry" as a registered OAuth application on startup with redirect URIs and OpenID scopes. Client ID/secret generated automatically and logged once.
3. **`version.py`** — Bumped to 0.1.1.

#### PRD Planner side (`crewai_productfeature_planner`)
1. **`sso_auth.py`** — Full rewrite:
   - RS256 JWT validation (was HS256) via `SSO_JWT_PUBLIC_KEY_PATH` or remote `/sso/oauth/introspect`.
   - `APP_NAME = "Idea Foundry"` constant; `app_id` claim enforcement when `SSO_EXPECTED_APP_ID` is set.
   - Webhook signature header changed to `X-Webhook-Signature` (was `X-SSO-Signature`) to match SSO service.
   - Returns enriched user dict with `app_id`, `app_name`, `enterprise_id`, `organization_id`.
2. **`sso_webhooks.py`** — Updated to handle all 6 SSO event types: `user.created`, `user.updated`, `user.deleted`, `login.success`, `login.failed`, `token.revoked`. Uses dispatch table pattern.
3. **`apis/__init__.py`** — FastAPI app title set to "Idea Foundry — CrewAI Product Feature Planner API". SSO webhook tag description updated.
4. **`.env.example`** — Full SSO configuration block: `SSO_ENABLED`, `SSO_BASE_URL`, `SSO_JWT_PUBLIC_KEY_PATH`, `SSO_ISSUER`, `SSO_EXPECTED_APP_ID`, `SSO_WEBHOOK_SECRET`.
5. **`version.py`** — Bumped to 0.23.0.
6. **`obsidian/Architecture/Environment Variables.md`** — Added SSO section.

### Tests
- 2272 passed (no regressions)

---

## Session 016 — CRUD APIs for Projects & Ideas
**Date**: 2026-03-16 | **Version**: 0.23.1 → 0.24.0

### Goal
Create REST CRUD and paginated list APIs for Projects and Ideas.

### Changes

1. **`apis/projects/router.py`** (new) — Full CRUD: `GET /projects` (paginated 10/25/50), `GET /projects/{id}`, `POST /projects`, `PATCH /projects/{id}`, `DELETE /projects/{id}`. SSO-protected. Pydantic request/response models.
2. **`apis/projects/__init__.py`** (new) — Package init with router re-export.
3. **`apis/ideas/router.py`** (new) — `GET /ideas` (paginated 10/25/50, filter by `project_id` & `status`), `GET /ideas/{run_id}`, `PATCH /ideas/{run_id}/status` (archive/pause). SSO-protected.
4. **`apis/ideas/__init__.py`** (new) — Package init with router re-export.
5. **`apis/__init__.py`** — Wired projects_router and ideas_router. Added OpenAPI tags.
6. **`version.py`** — Bumped to 0.24.0.
7. **`obsidian/APIs/API Overview.md`** — Added Projects and Ideas endpoint tables.
8. **`obsidian/Architecture/Module Map.md`** — Added projects/ and ideas/ entries.

### Tests
- 35 new tests (`tests/apis/projects/test_router.py`, `tests/apis/ideas/test_router.py`)
- 2307 total passed (no regressions)

---

## Session 017 — User Provisioning & user_id on All APIs
**Date**: 2026-03-17 | **Version**: 0.24.0 → 0.25.0

### Goal
Add user_id to all API endpoints for logged-in users. Auto-create user accounts from Slack profile when no existing account is found, leaving password empty for first web login.

### Changes

1. **mongodb/users/__init__.py** (new) — users MongoDB collection repository with CRUD operations.
2. **apis/user_provisioning.py** (new) — ensure_user_from_sso() and ensure_user_from_slack() for auto-provisioning.
3. **apis/sso_auth.py** — require_sso_user now calls ensure_user_from_sso(); returns DB user_id.
4. **apis/ideas/router.py** — All endpoints receive user dependency parameter.
5. **apis/projects/router.py** — All endpoints receive user dependency parameter.
6. **apis/prd/router.py** — All endpoints receive user dependency parameter.
7. **apis/prd/_route_actions.py** — All action endpoints receive user dependency.
8. **apis/publishing/router.py** — All endpoints receive user dependency parameter.
9. **apis/slack/_event_handlers.py** — app_mention and thread_message call ensure_user_from_slack().
10. **apis/slack/interactions_router/_dispatch.py** — Interactive handler calls ensure_user_from_slack().
11. **scripts/setup_mongodb.py** — Registered users collection with indexes.
12. **mongodb/__init__.py** — Re-exports all users repository symbols.
13. **tests/conftest.py** — Added users repo to mock DB patch targets.
14. **tests/apis/slack/conftest.py** (new) — Patches ensure_user_from_slack for Slack tests.
15. **tests/test_setup_mongodb.py** — Added users to expected collections set.
16. **version.py** — Bumped to 0.25.0.

### Tests
- 2307 passed (no regressions)

---

## Session 018 — Revert Local User Storage (SSO-Only Auth)
**Date**: 2026-03-17 | **Version**: 0.25.0 (corrected)

### Goal
User information must NOT be stored in the "ideas" database. All login/registration is handled by the external SSO portal. Users are redirected back to Idea Foundry after successful SSO auth. Reverted Session 017's local user provisioning system.

### Changes

1. **mongodb/users/__init__.py** (deleted) — Removed local users collection repository.
2. **apis/user_provisioning.py** (deleted) — Removed auto-provisioning module.
3. **tests/apis/slack/conftest.py** (deleted) — Removed provisioning mock fixture.
4. **apis/sso_auth.py** — Reverted to use SSO JWT `sub` claim directly as `user_id`. No local DB calls.
5. **apis/slack/_event_handlers.py** — Removed `ensure_user_from_slack` imports and calls from `_handle_app_mention` and `_handle_thread_message`.
6. **apis/slack/interactions_router/_dispatch.py** — Removed user provisioning block from interactive handler.
7. **mongodb/__init__.py** — Removed users imports, `USERS_COLLECTION`, and 8 user symbols from `__all__`.
8. **scripts/setup_mongodb.py** — Removed `USERS_COLLECTION` import and index definitions.
9. **tests/conftest.py** — Removed `_users_repo` import and patch target.
10. **tests/test_setup_mongodb.py** — Removed `"users"` from expected collections set.
11. **version.py** — Updated 0.25.0 codex entry to reflect SSO-only approach.
12. **obsidian/Database/MongoDB Schema.md** — Removed `users` collection (back to 8 collections).
13. **obsidian/Architecture/Module Map.md** — Removed `user_provisioning.py` entry.

### Architecture Clarification
- The "ideas" MongoDB database stores only application data (ideas, projects, sessions, jobs, etc.)
- User accounts, authentication, passwords, and registration belong exclusively to the SSO service
- API endpoints keep `user: dict = Depends(require_sso_user)` — identity comes from SSO JWT claims
- Slack users are identified by their Slack user ID (already tracked in `userSession` and `agentInteraction`)

### Tests
- 2303 passed (4 deselected: pre-existing `test_billing_error_not_retried` retry test issue)

---

## Session 019 — Logging Standard & Incident-Trace Instrumentation
**Date**: 2026-03-17 | **Version**: 0.25.0 → 0.26.0

### Goal
Establish a mandatory logging standard in the CODEX and implement it across all codebase modules, ensuring every business-logic file uses `get_logger(__name__)` and logs with trace identifiers for incident investigation.

### Changes

**Standards & Documentation:**
1. **CODEX.md** — Added § Logging Standard (Required): must use `get_logger`, log at boundaries, include trace context, use proper levels, `exc_info=True` on errors, no sensitive data.
2. **obsidian/Architecture/Coding Standards.md** — Added § 8 Logging Standard with 6 sub-sections: import pattern, what to log (table), trace context, error logging, security, exempt modules.

**Logger Import Standardization (41 files):**
3. Bulk-converted all `import logging` + `logging.getLogger(__name__)` to `from ...scripts.logging_config import get_logger` / `get_logger(__name__)` across: APIs (sso_auth, sso_webhooks, health, slack/*, publishing/*, ideas, projects), tools (slack_tools, slack_token_manager, openai_chat, gemini_chat), components (document), and all Slack interactive/session/interaction handlers.
4. Removed stale `import logging` from `apis/slack/router.py`.

**Incident-Trace Logging Added:**
5. **apis/health/router.py** — Added logger + trace logging to slack_token_status (team_id), slack_token_exchange (team_id + error), slack_token_refresh (team_id + success/fail).
6. **apis/projects/router.py** — Added logging to all 5 CRUD endpoints: get (project_id), create (name + project_id), update (project_id + fields), delete (project_id), with user_id on all.
7. **apis/ideas/router.py** — Added logging to get_idea (run_id) and update_idea_status (run_id + new_status + user_id).
8. **apis/sso_auth.py** — Added logging at auth boundary: bypass path, missing Bearer token, invalid/expired token, successful authentication (user_id + path).
9. **apis/publishing/service.py** — Added logging to list_pending_prds (count), publish_and_create_tickets (run_id), publish_all_and_create_tickets, get_delivery_status (run_id + not-found).
10. **tools/slack_tools.py** — Added channel/team_id/run_id to: token retrieval warning, token error refresh, send failure, read failure, post PRD result failure, file upload, interpret message entry/exit with intent.
11. **tools/openai_chat.py** — Added entry log (msg_len), exit log (intent + model), prefix all warnings/errors with `[OpenAI]`.
12. **tools/gemini_chat.py** — Added entry log (msg_len), exit log (intent + model), prefix all warnings/errors with `[Gemini]`.
13. **components/document.py** — Added debug log to assemble_prd_from_doc (run_id).

### Tests
- 2303 passed (4 deselected: pre-existing retry test)

---

## Session 020 — SERVER_ENV Three-Tier Public URL Resolution
**Date**: 2026-03-17 | **Version**: 0.26.0 → 0.27.0

### Goal
Wire `SERVER_ENV` (DEV/UAT/PROD) to control public URL resolution. Previously `.env` documented these variables but no Python code read them.

### Changes

**New Functions in `scripts/ngrok_tunnel.py`:**
1. `get_server_env()` — reads and validates `SERVER_ENV` (default DEV).
2. `is_dev()` — returns True when SERVER_ENV=DEV.
3. `get_public_url(port)` — DEV→start_tunnel, UAT→`https://{DOMAIN_NAME_UAT}`, PROD→`https://{DOMAIN_NAME_PROD}`. Auto-prepends https:// if scheme missing.

**main.py `start_api()` Rewired:**
4. Imports and uses `get_server_env`, `is_dev`, `get_public_url`, `start_tunnel`.
5. `--ngrok` flag kept as override. Logs SERVER_ENV on startup. Calls `update_slack_app_urls` for all environments.

**start_server.sh Rewired:**
6. Reads `ENV="${SERVER_ENV:-DEV}"`, only kills ngrok in DEV mode. Single command — no `--ngrok` flag needed.

**Documentation:**
7. `.env.example` — added SERVER_ENV, DOMAIN_NAME_UAT, DOMAIN_NAME_PROD with docs.
8. `slack_config.py` — docstring updated with SERVER_ENV info.
9. `obsidian/Architecture/Environment Variables.md` — added 3 new vars.
10. `obsidian/Changelog/Version History.md` — added v0.27.0.

### Tests
- 11 new tests in `test_ngrok_tunnel.py`: get_server_env (default, reads env, rejects invalid), is_dev (DEV/UAT/PROD), get_public_url (DEV tunnel, UAT domain, PROD domain, missing domain errors, https prepend, existing scheme).
- 2320 passed

---

## Session 021 — MongoDB Database Name Cleanup
**Date**: 2026-03-18 | **Version**: 0.27.0 → 0.27.1

### Goal
Make the MongoDB database name fully environment-driven and remove stale legacy vars.

### Changes
1. **migrate_to_atlas.py** — replaced inline `"ideas"` fallback with import of `DEFAULT_DB_NAME` from `client.py`.
2. **.env.example** — replaced stale MongoDB section (MONGODB_URI, MONGODB_PORT, MONGODB_USERNAME, MONGODB_PASSWORD) with `MONGODB_ATLAS_URI` + `MONGODB_DB` and docs for switching databases.
3. **README.md** — replaced 5 stale MongoDB env var rows with 2 correct ones (`MONGODB_ATLAS_URI`, `MONGODB_DB`).
4. **obsidian/Architecture/Environment Variables.md** — added guidance for switching DBs.
5. **obsidian/Database/MongoDB Schema.md** — added `MONGODB_DB` reference to header.
6. **obsidian/Changelog/Version History.md** — added v0.27.1.

### Security Hardening (Session 020b)
- Expanded .gitignore (4→40+ patterns: secrets, certs, Python artifacts, .bak, output/prds, obsidian/.obsidian, IDE).
- Untracked 40 files from git index (9 .bak, 27 output/prds, 4 obsidian config).
- Full secrets audit confirmed no real keys ever committed to git history.

### Tests
- 2320 passed

---

## Session 022 — Confluence Title Cleanup
**Date**: 2026-03-20 | **Version**: 0.27.1 → 0.28.0

### Goal
Replace `"PRD — {idea}"` Confluence/Jira page titles with the short-form idea text.

### Changes
1. **orchestrator/_helpers.py** — new `make_page_title(idea, fallback)` helper: strips, truncates to 80 chars with `…`, falls back to "Product Requirements".
2. **12 inline title sites replaced** across 9 files: `_confluence.py`, `_post_completion.py` (×2), `_startup_delivery.py`, `_startup_review.py` (×2), `_jira.py` (×2), `_cli_startup.py`, `publishing/service.py`, `publishing/watcher.py`, `components/startup.py`.
3. **publishing/models.py** — updated Field description example.
4. **17 test assertions updated** across 5 test files to match new title format.
5. **8 new tests** for `make_page_title` in `test_helpers.py`.

### Tests
- 2328 passed

---

## Session 023 — Confluence "Not Configured" Bug Fix
**Date**: 2026-03-20 | **Version**: 0.28.0 → 0.28.1

### Goal
Fix false-negative "Confluence credentials are not configured" error when
publishing from Slack, even when the channel's `projectConfig` has a valid
`confluence_space_key`.

### Root Cause
`_has_confluence_credentials()` called `_get_confluence_env()` with no args,
requiring all four env vars including `CONFLUENCE_SPACE_KEY`.  But space key
is a per-project routing parameter stored in MongoDB `projectConfig` and
resolved at publish time via `confluence_project_context` — not a global
env var.  The credential check ran **before** project config was loaded,
so it always failed when `CONFLUENCE_SPACE_KEY` wasn't in `.env`.

### Changes
1. **tools/confluence_tool.py** — rewrote `_has_confluence_credentials()` to
   only check the three Atlassian connection env vars (`ATLASSIAN_BASE_URL`,
   `ATLASSIAN_USERNAME`, `ATLASSIAN_API_TOKEN`).  `CONFLUENCE_SPACE_KEY` is
   no longer required at the credential-check gate.
2. **tests/orchestrator/test_helpers.py** — updated
   `TestHasConfluenceCredentials`: removed `CONFLUENCE_SPACE_KEY` from
   `test_all_set`, added `test_true_without_space_key` case.

### Tests
- 2329 passed

---

## Session 024 — Suppress Redundant Delivery Notification
**Date**: 2026-03-20 | **Version**: 0.28.1 → 0.28.2

### Goal
Fix unwanted "PRD Generation Complete" Slack notification when PRD is
fully delivered in the backend (Confluence + Jira both done).

### Root Cause
After the PRD flow finishes (including post-completion Confluence publish
and all Jira phases), `SlackPostPRDResultTool` posts a "PRD Generation
Complete" banner with ":white_check_mark: PRD has been generated
successfully!" — redundant because the user already received granular
progress messages for each delivery step (Confluence published, Jira
phase messages). The `predict_and_post_next_step("prd_completed")`
call fires immediately after, adding further noise.

### Changes
1. **interactive_handlers/_flow_runner.py** — skip `SlackPostPRDResultTool`
   and `predict_and_post_next_step` when `confluence_url` AND `jira_output`
   are both set (fully delivered).
2. **_flow_handlers.py** — same guard on the resume path.
3. **router.py** — same guard on the non-interactive flow path.

### Tests
- 2329 passed

---

## Session 025 — Route Feedback to Active PRD Flow
**Date**: 2026-03-20 | **Version**: 0.28.2 → 0.29.0

### Goal
Fix no response from orchestrator when user gives feedback during an
active PRD flow (e.g. "remove the avatar video references and focus
only on the compliances").

### Root Cause
`_handle_thread_message_inner` only routed thread replies to the active
flow when `pending_action` was in `_THREAD_REPLY_ACTIONS` (manual_refinement,
exec_summary_pre_feedback, exec_summary_feedback). During section
drafting, `pending_action` is `None` — so user feedback fell through to
`_interpret_and_act` (LLM intent classifier), which treated it as a new
command and responded with unrelated help text or silence.

### Changes
1. **interactive_handlers/_run_state.py** — new `_queued_feedback` dict,
   `queue_feedback(run_id, text)` and `drain_queued_feedback(run_id)`.
2. **_event_handlers.py** — restructured thread-reply matching: first
   checks if `pending_action` is in `_THREAD_REPLY_ACTIONS` (gate mode),
   then falls back to `queue_feedback` for any active run with
   `pending_action=None` (section drafting). Acknowledges with
   ":memo: Got it! I'll incorporate your feedback…".
3. **_event_handlers.py** — new `_safe_ack_reply` helper.
4. **flows/_section_loop.py** — at the top of each iteration, drains
   queued feedback and uses it as `user_feedback` (replaces AI critique).
5. **interactive_handlers/__init__.py** — exports `_queued_feedback`,
   `queue_feedback`, `drain_queued_feedback`.
6. **tests/apis/slack/conftest.py** — new autouse fixture to clear
   `_interactive_runs`, `_manual_refinement_text`, `_queued_feedback`
   between tests.

### Tests
- 2329 passed

---

## Session 026 — Fix Bot Not Engaging in Session Threads
**Date**: 2026-03-20 | **Version**: 0.29.0 → 0.29.1

### Goal
Fix bot not responding when user talks in a Slack session thread.
Expected outcome: bot should understand intent to start configuring
the project even after in-memory thread cache expires.

### Root Cause
The `should_process` gate in `events_router.py` silently dropped
thread messages when ALL 4 conditions were False:
1. `has_conversation` — in-memory thread cache expired after 10-min TTL
   or server restart
2. `has_interactive` — no active PRD flow in `_interactive_runs`
3. `has_pending` — no pending create/setup wizard
4. `has_active_session` — no project selected yet
   (`get_channel_project_id` returns None)

This meant any thread where the user hadn't selected a project yet
(wants to START configuring) became completely unresponsive after the
10-minute thread cache TTL.

### Changes
1. **mongodb/agent_interactions/repository.py** — new
   `has_bot_thread_history(channel, thread_ts)` checks
   `agentInteraction` collection for prior bot participation via
   `find_one({channel, thread_ts})`.
2. **mongodb/agent_interactions/__init__.py** — re-exports
   `has_bot_thread_history`.
3. **apis/slack/events_router.py** — added 5th fallback condition
   `has_thread_history` in `should_process` gate. Only checked when
   all other 4 conditions are False. When True, also re-registers
   the thread in the in-memory cache via `touch_thread()` to avoid
   repeated DB lookups.
4. **tests/apis/slack/test_dm_and_pending_routing.py** — 3 new tests
   in `TestThreadHistoryFallback`: dispatches when history exists,
   ignored when no history, re-registers in memory cache.
5. **tests/mongodb/agent_interactions/test_repository.py** — 3 new
   tests for `has_bot_thread_history`: found, not found, DB error.

### Tests
- 2335 passed

---

## Session 027 — Fix Bare 'configure' Intent Not Recognised
**Date**: 2026-03-20 | **Version**: 0.29.1 → 0.29.2

### Goal
Fix bare "configure" not being recognised as project configuration
intent. Admin types "configure" and expects the bot to start
project configuration.

### Root Cause
`_UPDATE_CONFIG_PHRASES` required at least two words (e.g. "configure
project", "project config"). The single word "configure" didn't match
any phrase in either `_UPDATE_CONFIG_PHRASES` or
`_CONFIGURE_MEMORY_PHRASES`, so it fell through to the LLM classifier
which also didn't map it to `update_config`.

### Changes
1. **_intent_phrases.py** — added "configure" to `_UPDATE_CONFIG_PHRASES`
2. **gemini_chat.py** — added `"configure" → update_config` example
3. **openai_chat.py** — added `"configure" → update_config` example
4. **tests/apis/slack/test_update_config_intent.py** — new test file
   with 5 tests: phrase fallback for bare "configure", phrase fallback
   for config phrases, "configure memory" still routes to
   configure_memory, bare "configure" dispatches to update_config
   handler, LLM update_config dispatches correctly.

### Tests
- 2340 passed

---

## Session 028 — 2026-03-20

**Scope**: All Commands Clickable — Interactive Buttons
**Date**: 2026-03-20 | **Version**: 0.29.2 → 0.30.0

### Goal
Replace all text-based "Say *command*" prompts with clickable Slack
Block Kit buttons so users never need to type command text.

### Changes
1. **blocks/_command_blocks.py** (NEW) — 11 button constants
   (BTN_LIST_IDEAS, BTN_LIST_PRODUCTS, BTN_CONFIGURE, etc.) and
   10 composite block builders (help_blocks, session_action_buttons,
   resume_prd_button, post_memory_saved_buttons, etc.)
2. **interactions_router/_command_handler.py** (NEW) — CMD_ACTIONS
   frozenset, _handle_command_action dispatcher routing cmd_* clicks
   to existing session/flow handlers, _handle_help with Block Kit.
3. **interactions_router/_dispatch.py** — Added _CMD_PREFIX and cmd_*
   dispatch block between session and memory actions.
4. **blocks/__init__.py** — Exported all new command block builders.
5. **interactions_router/__init__.py** — Exported CMD_ACTIONS and
   _handle_command_action.
6. **18 text replacements across 12 files**:
   - _session_blocks.py → session_action_buttons()
   - _memory_blocks.py → post_memory_saved_buttons(), post_memory_view_buttons()
   - _retry_blocks.py → removed "say resume prd flow" text
   - _product_list_blocks.py → product_list_footer_buttons()
   - _session_products.py → no_products_buttons()
   - _flow_handlers.py → BTN_LIST_IDEAS button, plain text fallback updated
   - _message_handler.py → help_blocks() with Block Kit
   - _next_step_handler.py → missing_keys_buttons(), check_publish_buttons()
   - _restart_handler.py → restart_cancelled_buttons()
   - _retry_handler.py → "Click Resume PRD" text
   - router.py → "Click Resume PRD" fallback text
   - _session_reply.py → INTRO_MESSAGE updated
   - apis/__init__.py → startup notification updated
7. **Test updates**: Fixed 3 existing tests for new block structure.
8. **33 new tests**: test_command_blocks.py (17), test_command_handler.py (16).

### Tests
- 2373 passed

---

## Session 029 — 2026-03-21

**Scope**: Complete Intent Button Coverage & Interaction-First Rule
**Date**: 2026-03-21 | **Version**: 0.30.0 → 0.30.1

### Goal
Audit all Slack intents and ensure every actionable one has a `cmd_*`
button. Codify the Interaction-First Rule so all future intents must
have clickable buttons.

### Audit Results
- 19 total LLM-recognised intents
- 11 already had buttons (from session 028)
- 5 actionable intents were missing buttons: `publish`, `create_jira`,
  `restart_prd`, `current_project`, `create_prd`
- 3 non-actionable intents (`greeting`, `general_question`, `unknown`)
  correctly excluded

### Changes
1. **blocks/_command_blocks.py** — Added 5 new button constants:
   BTN_PUBLISH, BTN_CREATE_JIRA, BTN_RESTART_PRD, BTN_CURRENT_PROJECT,
   BTN_NEW_IDEA. Updated help_blocks() from 2 to 4 action rows.
2. **interactions_router/_command_handler.py** — Added 5 new dispatch
   branches + updated CMD_ACTIONS (11 → 16).
3. **blocks/__init__.py** — Exported 5 new BTN_* constants.
4. **_message_handler.py** — Replaced fallback unknown-intent text
   ("type help for options") with New Idea + Help buttons.
5. **CODEX.md** — Added "Slack Interaction-First Rule" section with
   invariants, naming conventions, and checklist table.
6. **obsidian/Architecture/Coding Standards.md** — Added § 9 "Slack
   Interaction-First Rule" with required artifacts, naming convention,
   and forbidden patterns.

### Tests
- 2380 passed (7 new)

---

## Session 030 — 2026-03-21

**Scope**: Admin-Gated Project Configuration & Role-Aware Buttons
**Date**: 2026-03-21 | **Version**: 0.30.1 → 0.30.2

### Goal
Non-admin channel users should not be able to configure project settings,
switch projects, create projects, or configure knowledge/memory. Admin-only
buttons should be hidden from non-admin users in the help menu.

### Changes
1. **interactions_router/_command_handler.py** — Added `_ADMIN_ACTIONS`
   frozenset (cmd_configure_project, cmd_configure_memory,
   cmd_switch_project, cmd_create_project). Admin gate at top of
   `_handle_command_action()`. `_deny_non_admin()` helper.
   `_handle_help()` passes `is_admin` to `help_blocks()`.
2. **blocks/_command_blocks.py** — `help_blocks()` now accepts
   `is_admin` parameter. Admin-only buttons hidden for non-admins
   (4 action rows for admin, 3 for non-admin).
3. **_message_handler.py** — Added `can_manage_memory` gate before
   `update_config` intent handler. Help intent passes `is_admin`.
4. **interactions_router/_next_step_handler.py** — Added admin gate
   for `configure_memory` next-step accept path.

### Tests
- 2398 passed (18 new: 12 admin gate, 4 help blocks role, 2 next-step)

---

## Session 031 — 2026-03-21

**Scope**: Defense-in-Depth Admin Gates
**Date**: 2026-03-21 | **Version**: 0.30.2 → 0.30.3

### Goal
Add handler-level admin gates so non-admins are blocked regardless of
which caller invokes the handler (not just at the button dispatch level).

### Changes
- Added `can_manage_memory()` checks directly inside
  `handle_update_config`, `handle_configure_memory`,
  `handle_project_name_reply`, and `handle_project_setup_reply`.

### Tests
- 2398 passed

---

## Session 032 — 2026-03-21

**Scope**: Interaction-First Rule for ALL Slack Prompts
**Date**: 2026-03-21 | **Version**: 0.30.3 → 0.31.0

### Goal
Replace every instance where the bot tells users to "type", "say", or
"tell me" something with clickable Block Kit buttons. No user should
ever need to type to navigate the bot.

### Changes
1. **blocks/_session_blocks.py** — Setup wizard: added Skip button
   (`setup_skip` action) on all 5 steps. Setup-complete: replaced
   "just say" text with BTN_NEW_IDEA + BTN_CONFIGURE_MEMORY + BTN_HELP.
   Removed misleading "Type project name to search" text.
2. **blocks/_idea_list_blocks.py** — Footer: replaced context text
   "describe a new idea" with BTN_NEW_IDEA actions block.
3. **_session_ideas.py** — Empty ideas: replaced plain text with Block
   Kit message containing BTN_NEW_IDEA.
4. **interactions_router/_next_step_handler.py** — Added `_post_blocks()`
   helper. All accepted next-step suggestions now post action buttons
   (BTN_CONFIGURE, BTN_NEW_IDEA, BTN_HELP) instead of text.
5. **_message_handler.py** — Greeting posts Block Kit with BTN_NEW_IDEA +
   BTN_HELP instead of plain text.
6. **interactions_router/_dispatch.py** — Added `_SETUP_ACTIONS` frozenset
   with `setup_skip` routing to `handle_project_setup_reply`.
7. **CODEX.md** — Added "Interaction-First Testing" section with Block Kit
   testing methodology, checklist, and quick-check commands.

### Tests
- 26 new tests in `test_interaction_first_rule.py`
- Updated `test_idea_list.py` action block count assertions (+1 for footer)
- 2425 total tests

---

## Session 033 — 2026-03-21

**Scope**: Fix "configure tools" Misrouted to Project Config
**Date**: 2026-03-21 | **Version**: 0.31.0 → 0.31.1

### Problem
User typed "configure tools" expecting to manage the tools category in
project memory. Gemini correctly classified as `configure_memory`, but
the message handler's `update_config` condition caught it first because:
1. "configure" (bare) was in `_UPDATE_CONFIG_PHRASES` → `has_config_phrase` = True
2. No "tools" phrases existed in `_CONFIGURE_MEMORY_PHRASES` → `has_memory_phrase` = False
3. The `update_config` check `intent == "update_config" or (... and has_config_phrase)` fired first

### Changes
1. **`_intent_phrases.py`** — Added 15 "tools" phrases to
   `_CONFIGURE_MEMORY_PHRASES` (configure tools, add tools, manage tools,
   show tools, edit tools, etc.)
2. **`gemini_chat.py`** — Added 8 "tools" → configure_memory examples
   and added "tools" to the configure_memory description keywords
3. **`openai_chat.py`** — Same additions for parity
4. **`_message_handler.py`** — Changed update_config guard from
   `intent == "update_config" or (... and not has_memory_phrase ...)`
   to `not has_memory_phrase and (intent == "update_config" or ...)`
   so memory/tool phrases always override update_config, even when the
   LLM explicitly returns update_config

### Tests
- 4 new tests in `test_configure_memory_intent.py`
  (phrase fallback, correct dispatch, LLM override, negative check)
- 2429 total tests

---

## Session 034 — 2026-03-21

**Scope**: Slack File Upload Fallback for Truncated Content
**Date**: 2026-03-21 | **Version**: 0.31.1 → 0.31.2

### Problem
Slack Block Kit has a 3000-char limit per section text field. Long content
(idea refinements, exec summaries, requirements breakdowns) was silently
truncated at 2800 chars with only a "… (N more chars)" hint. Users could
not read the full output.

### Changes
1. **NEW `_slack_file_helper.py`** — shared utility module:
   - `truncate_with_file_hint(content, limit)` → `(preview, was_truncated)`
   - `upload_content_file(channel, thread_ts, content, filename, title)` → bool
2. **5 block builders** return `tuple[list[dict], bool]` instead of `list[dict]`:
   - `idea_approval_blocks`, `manual_refinement_prompt_blocks`,
     `requirements_approval_blocks`, `exec_summary_feedback_blocks`,
     `exec_summary_completion_blocks`
3. **8 caller sites** updated in `_flow_handlers.py` (3) and `_callbacks.py` (5)
   to unpack tuple and call `upload_content_file()` when truncated
4. **All test files** updated for tuple unpacking

### Tests
- 18 new tests in `test_slack_file_helper.py`
  (truncation helper, upload helper, was_truncated flag for all 5 builders)
- 2447 total tests

---

## Session 035 — 2026-03-21

**Scope**: Bot Only Responds When @Mentioned in Threads
**Date**: 2026-03-21 | **Version**: 0.31.2 → 0.32.0

### Problem
Bot was responding to all messages in threads where it had an active
session or thread history, even when the user did not @mention the bot.
Log showed user `U0AK24AU0F3` typing "configure" in a thread without
tagging the bot, and the bot classified it as `update_config` and
responded with the project setup wizard.

### Root Cause
The `events_router.py` thread follow-up logic had 5 conditions for
processing a message. The fallback conditions (`has_active_session` and
`has_thread_history`) were too permissive — they didn't require an
@mention. `has_active_session` is channel-level, not thread-level.

### Fix
Added `_bot_mentioned` check in events_router: fallback conditions
(`has_active_session`, `has_thread_history`) now require the bot to be
@mentioned in the message text. Active workflow conditions
(`has_interactive`, `has_pending`, `has_conversation`) remain
unrestricted since the user is replying to bot prompts.

When `bot_id` is unknown (e.g. no Slack client), the mention gate is
skipped to avoid breaking functionality.

### Tests
- 6 new tests in `test_dm_and_pending_routing.py`:
  - `TestMentionGateActiveSession` (no mention → ignored, with mention → dispatched)
  - `TestMentionGateThreadHistory` (no mention → ignored, with mention → dispatched)
  - `TestNoMentionGateForActiveWorkflows` (interactive + pending → dispatched without mention)
- 2453 total tests

---

## Session 036 — 2026-03-22

**Scope**: Fix File Upload Scope + Admin Cache TTL
**Date**: 2026-03-22 | **Version**: 0.32.0 → 0.32.1

### Problems
1. **File upload failing**: `files:write` scope missing from Slack manifest.
   Log showed: `missing_scope, needed: files:write`. The v0.31.2
   truncation+upload feature couldn't work in production.
2. **Admin status stale**: `_admin_cache` had no TTL (process-lifetime).
   User promoted from member to workspace admin was still blocked from
   configure actions. Log showed: `Admin check user=U0AK24AU0F3 → False`.
3. **Truncation overflow**: `exec_summary_completion_blocks` wraps preview
   in ~85-char prefix but used 2800 limit, risking overflow past 3000.

### Changes
1. **`slack_manifest.json`** — Added `files:write`, `files:read`,
   `pins:read`, `assistant:write`, `calls:read`, `calls:write` scopes
   (matching what the Slack app already has installed).
2. **`session_manager.py`** — Admin cache changed from `dict[str, bool]`
   to `dict[str, tuple[bool, float]]` with 5-minute TTL. Expired entries
   trigger a fresh Slack API call. `import time` added inside function.
3. **`_exec_summary_blocks.py`** — `exec_summary_completion_blocks` uses
   `truncate_with_file_hint(content, 2700)` instead of default 2800.

### Tests
- 3 new tests in `test_session_context.py`:
  - Cache TTL expired → re-checks Slack API
  - Cache TTL not expired → uses cached value
  - Role upgrade detected after TTL expires
- 1 updated assertion in `test_exec_summary_completion_gate.py`:
  combined section text <= 3000
- 2456 total tests

---

## Session 031 — 2026-03-22

**Scope**: Output file reorganisation & UX design file fix
**Version**: v0.32.1 → v0.33.0

### Problem
1. UX design markdown files were generated on every `run_ux_design()` call regardless of whether Figma actually produced a design — causing duplicate files.
2. All PRD and UX output files were stored in a flat `output/prds/YYYY/MM/` structure with no separation by project.

### Work Done
1. **UX file gating** (`flows/_ux_design.py`):
   - `_save_ux_design_file()` is now only called when `figma_url` is non-empty (Figma design successful).
   - Previously called unconditionally for every prompt/error/fallback output.

2. **Project-based output directories** (`flows/_finalization.py`, `flows/_ux_design.py`):
   - `finalize()` now saves PRDs to `output/{project_id}/product requirement documents/`
   - `save_progress()` uses `output/{project_id}/product requirement documents/_drafts/`
   - `_save_ux_design_file()` saves to `output/{project_id}/ux design/`
   - Falls back to legacy `output/prds/` when `project_id` is unavailable.

3. **`ux_output_file` MongoDB field** (`mongodb/working_ideas/_status.py`):
   - Added `get_ux_output_file()` and `save_ux_output_file()` functions.
   - UX file path is persisted with cleanup-on-replace logic (old file deleted when new one saved).
   - Exported via `repository.py` and `mongodb/__init__.py`.

4. **Startup disk scanner** (`orchestrator/_startup_review.py`):
   - `_discover_publishable_prds()` now scans both legacy `output/prds/` and `output/{project_id}/product requirement documents/` directories.

5. **Migration script** (`scripts/migrate_output_dirs.py`):
   - Queries workingIdeas documents with `output_file` or `ux_output_file` and `project_id`.
   - Moves files on disk and updates MongoDB references.
   - Supports `--dry-run` mode for preview.
   - Delete after running per project convention.

### Tests
- 7 new tests:
  - `test_file_saved_when_figma_url_present` — confirms file saved on successful Figma
  - `test_file_not_saved_when_prompt_only` — confirms no file for prompt-only
  - `test_file_not_saved_when_error_skipped` — confirms no file on skip/error
  - `test_file_uses_project_dir_when_available` — project_id passed to save function
  - `test_finalize_uses_project_dir_when_project_id_available` — PRD uses project dir
  - `test_save_progress_uses_project_dir_when_project_id_available` — drafts use project dir
  - (7th implicit: existing tests all updated with `resolve_project_id` patch)
- All existing tests updated to patch `resolve_project_id` in finalization module.
- 2463 total tests, all passing.

### Files Modified
- `src/.../flows/_ux_design.py` — Gate file generation, project-aware paths
- `src/.../flows/_finalization.py` — Project-aware output directories
- `src/.../mongodb/working_ideas/_status.py` — `get_ux_output_file`, `save_ux_output_file`
- `src/.../mongodb/working_ideas/repository.py` — Export new functions
- `src/.../mongodb/__init__.py` — Export new functions
- `src/.../orchestrator/_startup_review.py` — Scan project-based dirs
- `src/.../version.py` — v0.33.0
- `scripts/migrate_output_dirs.py` — NEW one-time migration script
- `tests/flows/test_ux_design.py` — 4 new tests
- `tests/flows/test_prd_flow.py` — 2 new tests + 7 updated tests
- `obsidian/Database/MongoDB Schema.md` — Added new fields
- `obsidian/Architecture/Module Map.md` — Added migration script
- `obsidian/Changelog/Version History.md` — v0.33.0 entry
- `obsidian/Sessions/Session Log.md` — This entry

---

## Session — 2026-03-22

**Scope**: Project Knowledge Base — Obsidian-style knowledge folders for agent learning
**Version**: v0.33.0 → v0.34.0

### Changes

1. **New module** (`scripts/project_knowledge.py`):
   - Generates `projects/{name}/{name}.md` overview pages with config, memory, tools, reference URLs, and wikilinks to completed ideas.
   - Generates `projects/{name}/ideas/{idea}.md` pages from workingIdeas docs with YAML frontmatter, full PRD sections in Obsidian format.
   - `load_completed_ideas_context()` queries MongoDB for completed ideas and formats summaries for agent backstory enrichment.
   - `sync_project_knowledge()` and `sync_completed_idea()` orchestrate page generation.

2. **Hooked into project creation** (`mongodb/project_config/repository.py`):
   - `create_project()` now calls `sync_project_knowledge()` after successful insert to bootstrap the project knowledge folder.

3. **Hooked into finalization** (`flows/_finalization.py`):
   - `finalize()` calls `sync_completed_idea()` after `mark_completed()` to generate the idea page and refresh the project overview.

4. **Integrated with memory loader** (`scripts/memory_loader.py`):
   - `enrich_backstory()` now also calls `load_completed_ideas_context()` so agents receive completed idea summaries in their backstory, avoiding duplication and creating synergy.

### Tests Added (34 new, 2496 total)
- `tests/test_project_knowledge.py` — 34 tests covering:
  - `_safe_dirname`, `_safe_filename`, `_truncate`, `_idea_title_from_doc` helpers
  - `generate_project_page` (basic, memory, URLs, ideas subdir, wikilinks)
  - `generate_idea_page` (basic, sections, Figma, delivery, original vs refined)
  - `load_completed_ideas_context` (with docs, no docs, empty ID, DB error)
  - `sync_project_knowledge` (creates page, no config)
  - `sync_completed_idea` (creates page, no doc, no project_id)
  - `enrich_backstory` integration (includes ideas, no ideas)

### Files Modified
- `src/.../scripts/project_knowledge.py` — NEW: Obsidian knowledge base builder
- `src/.../mongodb/project_config/repository.py` — Hook sync_project_knowledge into create_project
- `src/.../flows/_finalization.py` — Hook sync_completed_idea into finalize
- `src/.../scripts/memory_loader.py` — Integrate completed ideas into enrich_backstory
- `src/.../version.py` — v0.34.0
- `tests/test_project_knowledge.py` — NEW: 34 tests
- `obsidian/Architecture/Module Map.md` — Added project_knowledge.py
- `obsidian/Changelog/Version History.md` — v0.34.0 entry
- `obsidian/Sessions/Session Log.md` — This entry

---

## Session 055 — 2026-03-22

**Scope**: Engagement Manager Agent
**Version**: v0.34.0 → v0.35.0

### Work Done
- Created new CrewAI agent: **Engagement Manager** (`agents/engagement_manager/`)
  - YAML config: role, goal, backstory defining a navigation guide for unknown intents
  - Task config: engagement_response_task with template variables for user message, conversation history, active context, and available system actions
  - Python factory: `create_engagement_manager()` + `handle_unknown_intent()` runner
  - Uses `GEMINI_MODEL` (basic tier) — lightweight conversational routing, not deep reasoning
  - Override via `ENGAGEMENT_MANAGER_MODEL` env var
- Integrated into Slack message handler:
  - `unknown` intents now routed through the engagement manager agent instead of static fallback
  - Agent receives user message, conversation history, and active project context
  - Produces context-aware response with relevant action button suggestions
  - Graceful fallback to static help message if agent fails
  - `general_question` intents still use the LLM reply directly (kept separate)
  - Context-aware buttons: shows New Idea + Help (no project) or New Idea + List Ideas + Resume PRD + Help (with project)
- Added autouse mock fixture in `tests/apis/slack/conftest.py` to prevent real LLM calls in Slack tests
- Updated agents `conftest.py` to mock engagement manager LLM builder

### Tests Added (16 new, 2512 total)
- `tests/agents/test_engagement_manager.py`:
  - Factory: credentials required, accepts API key, accepts project, role content, no tools, no delegation, respects context window
  - LLM config: default model, ENGAGEMENT_MANAGER_MODEL override, GEMINI_MODEL fallback
  - YAML: agent.yaml loads with expected keys, tasks.yaml loads with template placeholders
  - Runner: returns response, passes history, includes context, propagates exceptions

### Files Modified
- `src/.../agents/engagement_manager/` — NEW: agent.py, __init__.py, config/agent.yaml, config/tasks.yaml
- `src/.../apis/slack/_message_handler.py` — Added `_handle_engagement_manager()`, `general_question` handler, replaced static fallback
- `src/.../version.py` — v0.35.0
- `tests/agents/test_engagement_manager.py` — NEW: 16 tests
- `tests/agents/conftest.py` — Added engagement manager LLM mock
- `tests/apis/slack/conftest.py` — Added engagement manager autouse mock
- `obsidian/Agents/Agent Roles.md` — Engagement Manager section
- `obsidian/Agents/LLM Model Tiers.md` — Added to Basic tier table
- `obsidian/Architecture/Module Map.md` — Added engagement_manager/ entry
- `obsidian/Architecture/Environment Variables.md` — Added ENGAGEMENT_MANAGER_MODEL
- `obsidian/Changelog/Version History.md` — v0.35.0 entry
- `obsidian/Sessions/Session Log.md` — This entry

---

## Session 056 — 2026-03-23

**Scope**: Fully Automated PRD Flow + Active-Flow Config Guard
**Version**: v0.35.0 → v0.36.0

### Work Done

**Feature 1 — Active-Flow Config Guard:**
- New `has_active_idea_flow(project_id)` MongoDB query in `_queries.py` — checks if any working idea with status "inprogress" exists for the project
- Guard in `_message_handler.py` — blocks `update_config` and `configure_memory` intents when an idea flow is active
- Guard in `_command_handler.py` — blocks `cmd_configure_project` and `cmd_configure_memory` button clicks during active flows
- Both guards post a denial message explaining the restriction with a View Ideas button

**Feature 2 — Fully Automated Flow:**
- Default mode switched from interactive to automated — keywords "interactive", "step-by-step", "manual", "walk me through" opt-in to interactive mode
- Three auto-mode gate factories in `_flow_handlers.py`:
  - `make_auto_exec_summary_gate()` — drains queued feedback, auto-approves
  - `make_auto_exec_completion_gate()` — posts note, returns True (continue)
  - `make_auto_requirements_gate()` — posts note, returns False (approved)
- Router branches on `auto_approve` to wire auto vs blocking gates
- Enhanced progress summaries — `section_iteration` and `exec_summary_iteration` events include `critique_summary` showing what the agent is working on
- Progress poster renders critique summaries as "What I'm working on:" blocks with feedback invitation

**Feature 3 — Auto-Resume on Server Restart:**
- New `find_resumable_on_startup()` in `_queries.py` — partitions unfinalized ideas into resumable (has Slack context) vs failed (no context)
- Startup lifespan in `apis/__init__.py` replaced `fail_unfinalized_on_startup()` with `find_resumable_on_startup()` + `_auto_resume_flows()`
- New `_run_slack_resume_flow()` in `router.py` — builds auto-mode callbacks, calls `resume_prd_flow`, posts completion/pause/error to original Slack thread

### Tests Added (29 new, 2541 total)
- `tests/apis/slack/test_active_flow_guard.py` — 13 tests
- `tests/apis/slack/test_automated_flow.py` — 16 tests
- Updated `test_exec_summary_completion_gate.py` — fixed regression + added auto-mode test
- Updated `test_interactive_default.py` — inverted defaults to match new automated-first behavior

### Files Modified
- `src/.../mongodb/working_ideas/_queries.py` — `has_active_idea_flow()`, `find_resumable_on_startup()`
- `src/.../mongodb/working_ideas/repository.py` — Exported new functions
- `src/.../apis/slack/_message_handler.py` — Flow guard, default mode switch
- `src/.../apis/slack/interactions_router/_command_handler.py` — Flow guard for config actions
- `src/.../apis/slack/_flow_handlers.py` — Auto-mode gate factories, enhanced progress
- `src/.../apis/slack/router.py` — Auto vs blocking gate branching, `_run_slack_resume_flow()`
- `src/.../flows/_executive_summary.py` — critique_summary in progress notification
- `src/.../flows/_section_loop.py` — critique_summary in progress notification
- `src/.../apis/__init__.py` — Auto-resume startup logic
- `src/.../version.py` — v0.36.0
- `tests/apis/slack/test_active_flow_guard.py` — NEW: 13 tests
- `tests/apis/slack/test_automated_flow.py` — NEW: 16 tests
- `tests/apis/slack/test_exec_summary_completion_gate.py` — Updated + 1 new test
- `tests/apis/slack/test_interactive_default.py` — Inverted default behavior tests
- `obsidian/Changelog/Version History.md` — v0.36.0 entry
- `obsidian/Sessions/Session Log.md` — This entry

---

## Session 057 — 2026-03-23

**Scope**: Server Crash-Prevention Hardening
**Version**: v0.36.0 → v0.37.0

### Work Done

**Comprehensive Reliability Audit:**
- Three sub-agent audits identified 26+ crash vectors across APIs, webhooks, tools
- Handler-level audit found 7/11 interaction handlers with no top-level protection

**_safe_handler() Wrapper (core pattern):**
- New `_safe_handler()` in `_dispatch.py` — wraps handler with team-id injection + try/except
- On exception: logs ERROR with `exc_info=True`, posts `:x: Something went wrong` to Slack channel/thread
- Swallows exception to keep thread pool healthy
- Replaced all 13 interaction handler dispatch calls from `_with_team` to `_safe_handler`

**Endpoint Protection:**
- Global exception handler enhanced with `exc_info=True` for full tracebacks
- PRD router: `list_resumable_runs`, `list_all_jobs`, `get_job` wrapped → HTTPException(500)
- PRD kickoff: `find_active_job()` wrapped → HTTPException(500)
- OAuth router: `_exchange_code` and `_apply_tokens` wrapped with catch-all handlers
- SSO webhooks: handler dispatch wrapped in try/except with traceback logging

**Tool-Level Fixes:**
- Jira `_http.py`: `json.JSONDecodeError` caught → `RuntimeError("Jira API returned invalid JSON")`
- Confluence `confluence_tool.py`: same pattern for invalid JSON responses

### Tests Added (14 new, 2560 total)
- `tests/apis/test_crash_prevention.py` — NEW: 14 tests covering _safe_handler, global exception handler, Jira/Confluence JSON decode, PRD router MongoDB failures

### Files Modified
- `src/.../apis/__init__.py` — `exc_info=True` in global exception handler
- `src/.../apis/slack/interactions_router/_dispatch.py` — `_safe_handler()` + 13 dispatch replacements
- `src/.../apis/sso_webhooks.py` — Handler dispatch wrapped
- `src/.../apis/slack/oauth_router.py` — _exchange_code and _apply_tokens hardened
- `src/.../apis/prd/router.py` — 3 MongoDB query endpoints protected
- `src/.../apis/prd/_route_actions.py` — kickoff find_active_job wrapped
- `src/.../tools/jira/_http.py` — JSONDecodeError catch
- `src/.../tools/confluence_tool.py` — JSONDecodeError catch
- `src/.../version.py` — v0.37.0
- `tests/apis/test_crash_prevention.py` — NEW: 14 tests
- `obsidian/Changelog/Version History.md` — v0.37.0 entry
- `obsidian/Sessions/Session Log.md` — This entry

---

## Session — 2026-03-24

**Scope**: Slack thread recovery & flow-aware summaries
**Version**: v0.37.0 → v0.37.1

### Bugs Fixed

**Issue #1 — Thread messages silently dropped after cache expiry**
- Auto-mode flows (default since v0.36.0) don't register in `_interactive_runs`
- After the 30-min in-memory cache TTL expires, thread messages were silently
  dropped at events_router.py line 404
- **Fix**: Added `find_idea_by_thread()` MongoDB query as a final fallback before
  dropping the message. Queries `workingIdeas` by `slack_channel` +
  `slack_thread_ts`. On match, re-registers the thread in cache via `touch_thread()`.

**Issue #2 — "Give me a summary" gets generic help instead of flow status**
- LLM classifier doesn't know about flow context, so "Give me a summary of the
  refined idea" → `general_question` → generic help text
- **Fix**: Added `_is_summary_request()` phrase detector (14 phrases) and
  `_build_flow_summary()` builder. When `general_question` + summary phrase +
  flow doc found → posts structured flow status with emoji, sections done/total,
  idea text, and section names.

### Files Modified
- `src/.../mongodb/working_ideas/_queries.py` — `find_idea_by_thread()` function
- `src/.../mongodb/working_ideas/repository.py` — export `find_idea_by_thread`
- `src/.../apis/slack/events_router.py` — `has_flow_thread` fallback check
- `src/.../apis/slack/_message_handler.py` — `_SUMMARY_PHRASES`, `_is_summary_request()`,
  `_build_flow_summary()`, flow-aware `general_question` handler
- `tests/apis/slack/test_flow_thread_routing.py` — NEW: 16 tests
- `src/.../version.py` — v0.37.1

### Tests
- 16 new tests (4 thread recovery, 2 phrase detection, 4 summary builder,
  3 integration, 3 MongoDB query)
- 2571 total (all passing, 0 failures)

---

## Session — 2026-03-30 (v0.46.1)

### Summary
Critical bug fix: Engagement Manager delivery failure detection and startup
Slack token validation. User reported EM not responding to messages.

### Root Cause Analysis
1. **Immediate cause**: Slack OAuth token expired for team T0AEH26MQRJ; refresh
   token invalid. All Slack API calls failed with `token_expired`.
2. **False-positive startup**: `get_valid_token()` returns expired tokens as a
   fallback (step 4), and startup only checked `if token:` (truthy) — never
   validated with `auth.test`. System reported "Slack token available" when it
   was unusable.
3. **Silent delivery failure**: EM agent generated responses correctly, but
   `chat.postMessage` failed → `send_tool.run()` fallback also failed → user saw
   NOTHING. No ERROR was logged for complete delivery failure.
4. **Not a v0.46.0 regression**: Knowledge sources changes did not touch Slack
   token management or message handler.

### Fixes Applied
1. **`_validate_slack_token()` in `apis/__init__.py`**: Extracted testable function
   that calls `auth.test` on startup. Logs ERROR for expired/revoked, WARNING for
   no token, INFO with team_id/bot_id for valid.
2. **Delivery failure tracking in `_handle_engagement_manager`**: Block Kit post
   failure now falls back to `send_tool.run()` with explicit error handling. Logs
   ERROR with 'DELIVERY FAILED' when both paths fail.

### Files Modified
- `src/.../apis/__init__.py` — `_validate_slack_token()` function, startup step 0b
- `src/.../apis/slack/_message_handler.py` — `_handle_engagement_manager` delivery tracking
- `src/.../version.py` — v0.46.1
- `tests/apis/slack/test_engagement_manager_response.py` — NEW: 28 regression tests

### Tests
- 28 new regression tests covering 7 invariants:
  - INVARIANT 1: EM always returns non-empty response (7 tests)
  - INVARIANT 2: EM always attempts Slack delivery (4 tests)
  - INVARIANT 3: ERROR logged on complete delivery failure (4 tests)
  - INVARIANT 4: Fast path → CrewAI fallback chain (3 tests)
  - INVARIANT 5: interpret_and_act error recovery (2 tests)
  - INVARIANT 6: Session context buttons (2 tests)
  - INVARIANT 7: Startup token validation (6 tests)
- 2681 total (all passing, 0 failures, 59s)

---

---

## Session — 2026-03-31 — Per-Section Model Tier Optimization (v0.48.1)

### Goal
Optimize section iteration by assigning appropriate LLM model tiers per section — research model for complex sections, basic model for structured/derivative sections.

### Analysis
All 9 iterable PRD sections were using the same research model (pro/o3) for drafting and refining. Sections like Dependencies and Assumptions are simple enumerative lists that don't need deep reasoning. This wastes ~44% of research-tier LLM calls.

### Changes (v0.48.1)
- **`apis/prd/_sections.py`** — New `SECTION_DRAFT_TIER` mapping: 5 research sections (problem_statement, user_personas, functional_requirements, no_functional_requirements, edge_cases) and 4 basic sections (error_handling, success_metrics, dependencies, assumptions). Added `get_section_draft_tier()`, `MODEL_TIER_RESEARCH`, `MODEL_TIER_BASIC` constants.
- **`agents/gemini_utils.py`** — Added `DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"` for basic-tier OpenAI sections.
- **`agents/product_manager/agent.py`** — `_build_llm()` and `create_product_manager()` accept `model_tier` parameter ("research"/"basic"). Basic tier uses flash/gpt-4.1-mini; research tier unchanged.
- **`flows/_agents.py`** — `get_available_agents()` accepts `model_tier` parameter, passes through to `create_product_manager()`.
- **`flows/prd_flow.py`** — Creates both research and basic agent sets at startup. Per-section tier selection via `get_section_draft_tier()` — selects basic or research agents before drafting and approval loop. Failed agent cleanup covers both agent sets.

### Tests
- 14 new tests in `test_product_manager.py`:
  - `TestSectionDraftTier` (6 tests): research/basic tier assignments, unknown defaults, all sections covered, constants
  - `TestBuildLlmModelTier` (7 tests): OpenAI/Gemini × research/basic, env var overrides, tier differentiation
  - `TestCreateProductManagerTier` (2 tests): basic tier agent creation, research default
- 2738 total (all passing)

### Documentation Updated
- `obsidian/Agents/LLM Model Tiers.md` — Added per-section model tier table, updated research model consumers
- `obsidian/Architecture/Environment Variables.md` — Updated `OPENAI_MODEL` description
- `obsidian/Changelog/Version History.md` — v0.48.1 entry
- `obsidian/Sessions/Session Log.md` — This entry

---

## Session — 2026-03-31 — Model Defaults & Test Performance Fixes (v0.48.2)

### Goal
1. Ensure all model names are env-driven (no hardcoded constants resolved at import time).
2. Fix slow test performance — all tests must run under 3 seconds.

### Root Causes Found
1. **Import-time env resolution in gemini_utils.py**: `DEFAULT_OPENAI_MODEL = os.environ.get("OPENAI_MODEL", ...)` froze the value at import time. When `.env` had `OPENAI_MODEL=o3`, the constant became `"o3"` forever — breaking PM model tier tests that used `monkeypatch.delenv("OPENAI_MODEL")`.
2. **Unmocked fast-path HTTP calls**: `handle_unknown_intent()`, `detect_user_steering()`, `handle_idea_query()` all try direct Gemini REST API first. Tests calling these without mocking the fast path attempted real HTTP calls, failing after ~1s each.
3. **Unmocked `predict_and_post_next_step`**: Jira intent tests called `_interpret_and_act()` which triggers `predict_and_post_next_step()` — makes real Gemini API + MongoDB calls.

### Changes (v0.48.2)
- **`agents/gemini_utils.py`** — Reverted DEFAULT_* constants to pure string fallbacks (no `os.environ.get()` at module level). Env lookup happens at call sites.
- **`tools/openai_chat.py`** — Uses centralized `DEFAULT_OPENAI_MODEL` from gemini_utils instead of inline `"gpt-4o-mini"`.
- **`.env.example`** — `OPENAI_MODEL=gpt-4.1-mini` (was `o3`), added `OPENAI_RESEARCH_MODEL=o3`, `GEMINI_RESEARCH_MODEL=gemini-3.1-pro-preview`.
- **`tests/agents/test_engagement_manager.py`** — Added `_skip_fast_path` autouse fixture mocking `_handle_unknown_intent_fast` and `_detect_user_steering_fast` to return None. Conditionally skips for `TestHandleUnknownIntentFastPath` and `TestDetectUserSteeringFastPath`.
- **`tests/agents/test_idea_agent.py`** — Added `_skip_fast_path` autouse fixture mocking `_handle_idea_query_fast`. Skips for `TestHandleIdeaQueryFastPath`.
- **`tests/apis/slack/test_create_jira_intent.py`** — Added `_no_slack_client` autouse fixture mocking `_get_slack_client` and `predict_and_post_next_step`.

### Performance Results
- EM tests: 20s → 3s (6.7× faster)
- IA tests: 5s → 2s (2.5× faster)
- All tests under 3s threshold in isolated runs

### Tests
- 158 tests in changed files all passing (0 failures)
- 2738 total tests passing (3 pre-existing flaky failures unrelated to changes)

### Documentation Updated
- `obsidian/Changelog/Version History.md` — v0.48.2 entry
- `obsidian/Sessions/Session Log.md` — This entry

---

## Session: 2026-04-08 — Gap Ticket Backend Features (v0.59.0)

### Goal
Implement backend features for 4 open gap tickets with complete user answers. Fix test patch targets. Update all documentation.

### Changes (v0.59.0)

**New Files:**
- `apis/prd/_route_timeline.py` — `GET /flow/runs/{run_id}/timeline` unified PRD journey timeline. Stitches workingIdeas, crewJobs, agentInteraction, productRequirements into chronological TimelineEvent list.
- `apis/prd/_route_versions.py` — `GET /flow/runs/{run_id}/versions` PRD version history. Returns VersionHistoryResponse with section content snapshots and changelogs.
- `tests/apis/prd/test_timeline.py` — 9 tests for timeline builder and response models.
- `tests/apis/publishing/test_confluence_preview.py` — 5 tests for confluence preview service.
- `tests/mongodb/test_version_tracking.py` — 5 tests for version snapshot repository functions.
- `tests/mongodb/test_section_conversations.py` — 11 tests for section conversation storage.

**Modified Files:**
- `apis/prd/router.py` — Added timeline_router and versions_router includes.
- `apis/publishing/router.py` — Added `GET /publishing/confluence/{run_id}/preview` endpoint.
- `apis/publishing/service.py` — Added `preview_confluence_content()` function.
- `apis/publishing/models.py` — Added `ConfluencePreviewResponse` model.
- `mongodb/product_requirements/repository.py` — Added `save_version_snapshot()`, `get_version_history()`, `get_current_version()`.
- `mongodb/product_requirements/__init__.py` — Re-exports for version functions.
- `mongodb/working_ideas/_sections.py` — Added `save_section_message()`, `get_section_conversation()`, `get_section_summary_notes()`, `save_section_summary_note()` with injection guards.
- `mongodb/working_ideas/repository.py` — Re-exports for section conversation functions.
- `version.py` — v0.59.0 CodexEntry.

**Gap Tickets Updated:**
- `GAP-flow-confluence-publishing-preview.md` — status: in-progress, v0.59.0 backend foundation
- `GAP-flow-journey-dashboard-history.md` — status: in-progress, v0.59.0 backend foundation
- `GAP-flow-prd-iteration-versioning.md` — status: in-progress, v0.59.0 backend foundation
- `GAP-flow-section-drafting-conversation.md` — status: in-progress, v0.59.0 backend foundation

### Tests
- 30 new tests all passing
- 2807 total tests passing (0 failures) in 481s

### Documentation Updated
- `obsidian/Architecture/Module Map.md` — Added _route_timeline.py, _route_versions.py
- `obsidian/Changelog/Version History.md` — v0.59.0 entry
- `obsidian/APIs/PRD Flow/GET flow-runs-{run_id}-timeline.md` — New per-route doc
- `obsidian/APIs/PRD Flow/GET flow-runs-{run_id}-versions.md` — New per-route doc
- `obsidian/APIs/Publishing/GET publishing-confluence-{run_id}-preview.md` — New per-route doc
- `obsidian/Sessions/Session Log.md` — This entry

---

## Session — 2026-04-07 (v0.59.5)

**Focus:** Fix GET /flow/runs/{run_id} returning 404 after server restart

### Root Cause
- `GET /flow/runs/{run_id}` only checked the in-memory `runs` dict (`dict[str, FlowRun]`)
- This dict is ephemeral — lost on every server restart
- Run data IS persisted in MongoDB (crewJobs + workingIdeas collections) but no fallback existed

### Changes
- **router.py**: Added `_build_run_response()` and `_build_run_response_from_db()` helpers
  - `_build_run_response()`: handles active in-memory runs (existing behaviour)
  - `_build_run_response_from_db()`: queries crewJobs for metadata, calls `restore_prd_state()` for draft content
- **router.py (list_runs)**: Now supplements in-memory runs with persistent MongoDB jobs via `list_jobs()`
- **version.py**: Bumped to v0.59.5

### Tests
- Updated `test_get_run_status_not_found` to patch `find_job`
- Added `test_get_run_status_falls_back_to_mongodb` — DB fallback with empty draft
- Updated `test_list_runs_empty` and `test_list_runs_with_data` to patch `list_jobs`
- Added `test_list_runs_includes_mongodb_jobs` — dedup in-memory + DB
- 2458 passed (1 pre-existing failure in test_retry.py, unrelated)

---

## Session — 2026-04-07 (v0.60.0)

**Focus:** User Feedback gap ticket resolution — wire backend to flow, clean up gap files

### Gap Tickets Processed (8 total)

**Fully answered → Implemented + deleted (4):**
1. **confluence-publishing-preview** — Version snapshot on Confluence publish, change detection
2. **journey-dashboard-history** — `section_approved` decision annotations in timeline API
3. **prd-iteration-versioning** — `save_version_snapshot()` wired into `finalize()` and `_apply()`
4. **section-drafting-conversation** — `save_section_message()` wired into section loop (user feedback + agent critiques), `save_section_summary_note()` on approval

**Partially answered → New clarity gap files created + originals deleted (4):**
5. **engineering-plan-context** → `GAP-flow-engineering-plan-tech-level.md` (Q2: tech-level assessment)
6. **idea-refinement-interactivity** → `GAP-flow-idea-refinement-options-frequency.md` (Q3: 3 options frequency)
7. **jira-ticketing-interactivity** → `GAP-flow-jira-kanban-structure.md` (Q1: Kanban interpretation)
8. **webapp-frontend-framework** → `GAP-webapp-monorepo-decision.md` (Q4: monorepo vs separate)

### Code Changes

**_finalization.py**:
- After `mark_completed()`, calls `save_version_snapshot()` to persist v1 (or vN) snapshot with all section content

**_section_loop.py**:
- Added `_save_msg()` helper — best-effort `save_section_message()` calls
- Added `_save_summary()` helper — best-effort `save_section_summary_note()` calls
- User approval → saves `[Approved]` message + summary note
- User critique feedback → saves feedback as `user` role message
- Agent critique → saves critique as `agent` role message
- Auto-approval paths (max iterations, SECTION_READY) → saves summary note

**_confluence.py**:
- After `upsert_delivery_record()` in `_apply()`, calls `save_version_snapshot()` with changelog noting the Confluence URL

**_route_timeline.py**:
- After iterating section drafts, emits a `section_approved` `TimelineEvent` with iteration count

### Tests
- 375 affected tests pass (flows, orchestrator, timeline)
- No regressions introduced

---

## Session: 2026-04-08 — Test Suite Optimization (v0.61.1)

### Goal
Full regression test suite was taking 480s (8 min). Optimize to bring every test under 1.5s and fix flaky tests.

### Root Causes Identified
1. **Cold Agent creation**: First `Agent()` costs 1.2s due to pydantic `model_rebuild()`; subsequent only 0.12s
2. **Unmocked LLM builders**: UX Designer, Product Manager, and PM Critic `_build_llm()` functions creating real `LLM` objects in tests
3. **State leakage**: `session_manager` pending dicts and `events_router` caches not cleaned between Slack tests
4. **Assert scope**: Retry shutdown tests asserting `mock_sleep.assert_not_called()` outside the mock context — background threads cause false positives

### Changes Made

**tests/conftest.py**:
- Added `_warm_crewai_agent` session-scoped fixture — creates one throwaway Agent to warm pydantic model hierarchy (saves ~1.2s per first-agent-creation per module)

**tests/agents/conftest.py**:
- Added `_build_llm` mock for Product Manager agent
- Added `_build_critic_llm` mock for Product Manager Critic agent
- Added `_build_llm` mock for UX Designer agent

**tests/flows/conftest.py** (NEW):
- Autouse fixture mocking `_build_llm` for UX Designer, Product Manager, and PM Critic in flow tests

**tests/apis/slack/conftest.py**:
- Added `_clear_session_manager_state` autouse fixture — clears `_pending_project_creates`, `_pending_memory_entries`, `_pending_project_setup` before and after each test
- Also clears `events_router._seen_events`, `_thread_conversations`, `_thread_last_active`

**tests/test_retry.py**:
- Moved `assert crew.kickoff.call_count` and `mock_sleep.assert_not_called()` inside the mock context for `test_shutdown_interpreter_not_retried` and `test_shutdown_futures_not_retried`

### Results
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Total suite time | 480s (8 min) | 45s | **90.5%** |
| Slowest test | 12.42s | 1.00s | **92%** |
| Tests > 1.5s | 30+ | **0** | Target met |
| Failures | 4 flaky | **0** | All fixed |
| Test count | 2819 | 2819 | No removals |

---

## Session — 2026-04-10 (continued) — v0.65.0

### Goal
Implement missing APIs identified in the web-app Gap Analysis (A1–A3).

### Changes

**v0.65.0 — Web-App API Gap Closure**

1. **`GET /dashboard/stats`** (A1 — P1):
   - New `apis/dashboard/` module with router
   - MongoDB aggregation pipeline: `total_ideas`, `in_development`, `prd_completed`, `ideas_in_progress`, `uxd_completed`
   - Graceful degradation: returns zeros on DB error
   - 4 tests

2. **`POST /flow/ux/kickoff`** (A2 — P2):
   - Web-app-compatible endpoint accepting `run_id` in request body
   - Delegates to existing `POST /flow/ux-design/{run_id}` logic
   - 5 tests

3. **`GET /flow/ux/status/{run_id}`** (A3 — P2):
   - Returns `UXDesignStatusResponse` with fields matching frontend `UxDesignStatus` interface
   - Derives boolean flags from stored `ux_design_status` string
   - Falls back to `figma_design_status` field
   - 8 tests

4. **`GET /flow/runs/{run_id}` fix**:
   - DB fallback path now includes `ux_design_status` and `ux_design_content` from workingIdeas doc
   - 2 tests

### Files Modified
- `src/.../apis/dashboard/__init__.py` — New module
- `src/.../apis/dashboard/router.py` — New: `GET /dashboard/stats`
- `src/.../apis/prd/_route_ux_design.py` — Added `POST /flow/ux/kickoff`, `GET /flow/ux/status/{run_id}`
- `src/.../apis/prd/router.py` — Fixed `_build_run_response_from_db` to include UX design fields
- `src/.../apis/__init__.py` — Registered `dashboard_router`
- `tests/apis/dashboard/test_router.py` — 4 new tests
- `tests/apis/prd/test_ux_design_web.py` — 13 new tests
- `tests/apis/prd/test_prd.py` — 2 new tests
- `version.py` — v0.65.0
- `obsidian/Changelog/Version History.md` — Entry added
- `obsidian/Architecture/Module Map.md` — dashboard/ added
- `obsidian/APIs/API Overview.md` — Dashboard section + UX endpoints added

### Test Results
- 2900 passed, 0 failed (46s)

---

## Session — 2026-04-11 — v0.66.0

### Goal
Process user answers from GAP-api-remaining-webapp-gaps.md (A4→R3, A6→R3).

### User Answers
- **S1 (A4)**: R3 — Local preferences only. `PATCH /user/profile` already exists.
- **S2 (A6)**: R3 — Full bidirectional WebSocket.
- **A5**: Frontend-only fix (backend already has `GET /integrations/status`).

### Changes

**v0.66.0 — WebSocket Real-Time Agent Activity (Gap A6)**

1. **`WS /flow/runs/{run_id}/ws`** (A6 — P3):
   - Bidirectional WebSocket endpoint for real-time flow run updates
   - Sends `status_update`, `agent_activity`, `progress`, `complete` events
   - Accepts client messages: `ping` (→ pong), `get_status` (→ snapshot)
   - Background polling loop queries agentInteractions for new events
   - `broadcast_sync()` helper for thread-safe push from background tasks
   - Connection hub with async lock for safe multi-client management
   - `_enable_poll_loop` flag for test isolation
   - 10 tests (connect, status, ping/pong, get_status, error handling, db fallback)

2. **Gap A4** — confirmed already resolved: `PATCH /user/profile` exists at `user_profile/router.py` with `display_name`, `default_project_id`, `timezone`, `notification_preferences` fields.

3. **Gap A5** — no backend work needed, `GET /integrations/status` already returns Confluence + Jira connection details.

### Files Modified
- `src/.../apis/prd/_route_websocket.py` — New: WebSocket endpoint + hub + poll loop
- `src/.../apis/prd/router.py` — Added `ws_router` import + `ws_only_router`
- `src/.../apis/__init__.py` — Registered `prd_ws_router`
- `tests/apis/prd/test_websocket.py` — 10 new tests
- `version.py` — v0.66.0
- `obsidian/Changelog/Version History.md` — Entry added
- `obsidian/Architecture/Module Map.md` — `_route_websocket.py` added
- `obsidian/APIs/API Overview.md` — WS endpoint added (14 PRD endpoints total)
- `obsidian/User Feedback/GAP-api-remaining-webapp-gaps.md` — Deleted (all resolved)

---

### v0.67.0 — Fix critical bug: project_id validation (2026-04-11)

**Task:** Investigate and fix "proj-1" continuously running. Prevent
stale/phantom project IDs from creating orphaned ideas.

**Root cause:** No validation that `project_id` exists in `projectConfig`
when kicking off a PRD flow. Both the API (`POST /flow/prd/kickoff`)
and Slack kickoff accepted arbitrary strings, allowing 67 orphaned
ideas to accumulate for the non-existent "proj-1" project over 12 days.

**Changes:**

- `apis/prd/_route_actions.py` — Validate project_id exists via
  `get_project()` before kickoff. Returns 422 if not found.
- `apis/slack/router.py` — Validate project_id in `_run_slack_prd_flow()`.
  Logs warning and clears invalid project_id to prevent persistence.
- `mongodb/working_ideas/_status.py` — Defence-in-depth in
  `save_project_ref()`: rejects writes for non-existent projects.

**Files modified:**

- `src/.../apis/prd/_route_actions.py` — project_id validation
- `src/.../apis/slack/router.py` — Slack project_id validation
- `src/.../mongodb/working_ideas/_status.py` — save_project_ref validation
- `tests/apis/prd/test_prd.py` — 3 new tests (invalid, valid, skipped)
- `tests/mongodb/working_ideas/test_repository.py` — 1 new test + updated 4 existing
- `version.py` — v0.67.0
- `obsidian/Changelog/Version History.md` — Entry added
- `obsidian/User Feedback/GAP-stale-project-proj1-cleanup.md` — Created for user decisions

---